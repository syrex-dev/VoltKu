import asyncio
import functools
import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from telegram import Bot, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from app.config import get_settings
from app.constants import OFFLINE_THRESHOLD_SECONDS
from app.db import SessionLocal
from app.models import Anomaly, Device, Reading, Setting
from app.mqtt_ingest import get_device_status
from app.services.notifier import set_notification_sender
from app.services.reports import calculate_device_forecast, calculate_device_summary

# Konfigurasi logging: httpx dan telegram pada level WARNING agar tidak membocorkan token
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

TZ_WIB = ZoneInfo("Asia/Jakarta")

@dataclass
class ChatRetryItem:
    event_key: str
    chat_id: int
    message: str
    attempts: int
    next_retry: float
    created_at: float


_bot_app: Optional[Application] = None
_last_send_times: dict[int, float] = {}
_send_lock = asyncio.Lock()
_retry_queue: list[ChatRetryItem] = []
_delivered_events: dict[str, dict] = {}


def _clear_delivery_state() -> None:
    """Helper untuk membersihkan riwayat pengiriman per chat (digunakan pada pengujian)."""
    _delivered_events.clear()
    _retry_queue.clear()


def _format_id_number(val: float, decimals: int = 3) -> str:
    fmt_str = f"{{:,.{decimals}f}}"
    formatted = fmt_str.format(val)
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def _format_rupiah(rp: int) -> str:
    return f"Rp{rp:,}".replace(",", ".")


def _format_time_wib(epoch_sec: int) -> str:
    return datetime.fromtimestamp(epoch_sec, tz=TZ_WIB).strftime("%H:%M:%S")


def _format_datetime_wib(epoch_sec: int) -> str:
    return datetime.fromtimestamp(epoch_sec, tz=TZ_WIB).strftime("%d/%m/%Y %H:%M:%S")


async def send_message_rate_limited(bot: Bot, chat_id: int, text: str) -> None:
    """Kirim plain text ke chat_id dengan rate limit <= 1 msg/s/chat dan truncate pada 4096 char."""
    if len(text) > 4096:
        text = text[:4093] + "..."

    async with _send_lock:
        now = time.monotonic()
        last_time = _last_send_times.get(chat_id, 0.0)
        elapsed = now - last_time
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        await bot.send_message(chat_id=chat_id, text=text)
        _last_send_times[chat_id] = time.monotonic()


def process_chat_retry_queue_sync(bot: Optional[Bot] = None) -> int:
    """Memproses antrean retry per chat secara otomatis pada background tick:
    - Backoff eksponensial (15s, 30s, 60s, 120s, maks 300s).
    - Maksimal 5 percobaan.
    - Kedaluwarsa 1 jam (3600 detik).
    - Log tanpa membocorkan token bot.
    - Mengembalikan jumlah pesan yang berhasil terkirim pada tick ini.
    """
    global _bot_app, _retry_queue, _delivered_events
    if not _retry_queue:
        return 0

    if bot is None:
        if _bot_app is None or not _bot_app.bot:
            return 0
        bot = _bot_app.bot

    settings = get_settings()
    now_wall = time.time()
    now_mono = time.monotonic()

    remaining_queue: list[ChatRetryItem] = []
    items_to_attempt: list[ChatRetryItem] = []

    for item in _retry_queue:
        if (now_wall - item.created_at) > 3600.0:
            logger.warning(
                "Retry chat %s untuk event %s dibatalkan (kedaluwarsa 1 jam)",
                item.chat_id,
                item.event_key,
            )
            continue
        if item.attempts > 5:
            logger.warning(
                "Retry chat %s untuk event %s dibatalkan (mencapai batas 5 percobaan)",
                item.chat_id,
                item.event_key,
            )
            continue

        evt_delivered = _delivered_events.get(item.event_key, {}).get("chats", set())
        if item.chat_id in evt_delivered:
            continue

        if now_mono >= item.next_retry:
            items_to_attempt.append(item)
        else:
            remaining_queue.append(item)

    _retry_queue[:] = remaining_queue
    if not items_to_attempt:
        return 0

    success_count = 0

    async def _run_retries():
        nonlocal success_count
        for it in items_to_attempt:
            try:
                await send_message_rate_limited(bot, it.chat_id, it.message)
                evt_info = _delivered_events.setdefault(
                    it.event_key, {"chats": set(), "created_at": now_wall}
                )
                evt_info["chats"].add(it.chat_id)
                success_count += 1
                logger.info(
                    "Retry telegram berhasil terkirim ke chat %s untuk event %s",
                    it.chat_id,
                    it.event_key,
                )
            except Exception as err:
                safe_err = str(err)
                if settings.telegram_bot_token and settings.telegram_bot_token in safe_err:
                    safe_err = safe_err.replace(settings.telegram_bot_token, "[REDACTED]")
                it.attempts += 1
                delay = min(300.0, 15.0 * (2 ** min(it.attempts - 1, 5)))
                it.next_retry = time.monotonic() + delay
                logger.warning(
                    "Retry telegram ke chat %s gagal: %s (percobaan %d/5, backoff %.1fs)",
                    it.chat_id,
                    safe_err,
                    it.attempts,
                    delay,
                )
                _retry_queue.append(it)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            try:
                pool.submit(lambda: asyncio.run(_run_retries())).result(timeout=10.0)
            except Exception as e:
                logger.error("Error processing retry queue: %s", e)
    else:
        asyncio.run(_run_retries())

    return success_count


def send_telegram_broadcast_sync(message: str, event_key: Optional[str] = None) -> bool:
    """Mengirim pesan notifikasi plain text ke seluruh chat di TELEGRAM_ALLOWED_CHAT_IDS.

    - Menggunakan dedup berbasis event_key (alert/report + context + seq).
    - Chat yang sudah menerima pesan ini tidak akan dikirimi lagi.
    - Chat yang gagal akan didaftarkan ke antrean retry otomatis per-chat.
    - Mengembalikan True jika terkirim ke >= 1 chat. Jika seluruhnya gagal, mengembalikan False.
    """
    global _bot_app, _delivered_events, _retry_queue
    bot_app = _bot_app
    if bot_app is None or not bot_app.bot:
        return False

    settings = get_settings()
    chat_ids = settings.allowed_chat_id_list
    if not chat_ids:
        return False

    bot = bot_app.bot

    if not event_key:
        event_key = f"msg:{hashlib.sha256(message.encode('utf-8')).hexdigest()}"

    now_wall = time.time()
    # TTL 24 jam & batasi ukuran cache dedup maks 1000 item
    if len(_delivered_events) > 1000:
        cutoff = now_wall - 86400.0
        _delivered_events = {
            k: v for k, v in _delivered_events.items() if v.get("created_at", 0) >= cutoff
        }

    evt_info = _delivered_events.setdefault(
        event_key, {"chats": set(), "created_at": now_wall}
    )
    delivered_chats: set[int] = evt_info["chats"]

    async def _send_all() -> bool:
        now_mono = time.monotonic()
        for cid in chat_ids:
            if cid in delivered_chats:
                continue

            try:
                await send_message_rate_limited(bot, cid, message)
                delivered_chats.add(cid)
            except Exception as err:
                safe_err = str(err)
                if settings.telegram_bot_token and settings.telegram_bot_token in safe_err:
                    safe_err = safe_err.replace(settings.telegram_bot_token, "[REDACTED]")
                logger.warning(
                    "Gagal mengirim notifikasi telegram ke chat %s untuk event %s: %s "
                    "(masuk antrean retry)",
                    cid,
                    event_key,
                    safe_err,
                )
                _retry_queue.append(
                    ChatRetryItem(
                        event_key=event_key,
                        chat_id=cid,
                        message=message,
                        attempts=1,
                        next_retry=now_mono + 15.0,
                        created_at=now_wall,
                    )
                )

        return len(delivered_chats) >= 1

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            try:
                return pool.submit(lambda: asyncio.run(_send_all())).result(timeout=10.0)
            except Exception as err:
                logger.error("Gagal broadcast notifikasi telegram: %s", err)
                return False
    else:
        return asyncio.run(_send_all())


def allowlist_only(func):
    """Decorator otorisasi: abaikan chat asing (silent drop) tanpa log chat_id, token, atau isi."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.effective_chat:
            return
        chat_id = update.effective_chat.id
        settings = get_settings()
        allowed = settings.allowed_chat_id_list
        if not allowed or chat_id not in allowed:
            # Silent drop tanpa mencatat chat_id atau isi pesan
            return
        return await func(update, context)

    return wrapper


def _get_target_devices(session, args: list[str]) -> tuple[list[Device], Optional[str]]:
    """Helper untuk memfilter perangkat target (spesifik atau seluruh non-sim)."""
    settings = get_settings()
    if args:
        target_id = args[0].strip()
        dev = session.get(Device, target_id)
        if not dev:
            return [], f"Perangkat '{target_id}' tidak ditemukan."
        return [dev], None

    exclude_prefixes = [
        p.strip() for p in settings.alert_exclude_device_prefixes.split(",") if p.strip()
    ]
    devices = session.scalars(select(Device).order_by(Device.id.asc())).all()
    eligible = [d for d in devices if not any(d.id.startswith(p) for p in exclude_prefixes)]
    if not eligible:
        return [], "Tidak ada perangkat terdaftar (atau semua perangkat adalah simulasi)."
    return eligible, None


# ==============================================================================
# COMMAND HANDLERS
# ==============================================================================

@allowlist_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = (
        "⚡ Halo! Saya bot Monitor Listrik Pintar.\n\n"
        "Perintah yang tersedia:\n"
        "• /now [id] - Cek daya & kondisi listrik saat ini\n"
        "• /today [id] - Ringkasan pemakaian hari ini\n"
        "• /week [id] - Ringkasan pemakaian minggu ini\n"
        "• /month [id] - Ringkasan pemakaian bulan ini\n"
        "• /forecast [id] - Proyeksi tagihan akhir bulan\n"
        "• /anomali [id] - Riwayat peringatan 7 hari terakhir\n"
        "• /perangkat - Daftar perangkat terdaftar\n"
        "• /tarif <Rp/kWh> - Ubah tarif listrik PLN\n"
        "• /batas <Watt> - Ubah batas daya peringatan\n"
        "• /laporan on|off - Aktifkan/nonaktifkan laporan berkala\n\n"
        "Tip: Tanpa parameter [id], bot akan menampilkan ringkasan seluruh perangkat."
    )
    await send_message_rate_limited(context.bot, update.effective_chat.id, msg)


@allowlist_only
async def cmd_perangkat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with SessionLocal() as session:
        devices = session.scalars(select(Device).order_by(Device.id.asc())).all()
        if not devices:
            text = "Belum ada perangkat terdaftar di sistem."
        else:
            lines = ["📋 Daftar Perangkat Terdaftar:"]
            for d in devices:
                seen_str = _format_datetime_wib(d.last_seen_at) if d.last_seen_at else "Belum ada"
                st = get_device_status(d, threshold_seconds=OFFLINE_THRESHOLD_SECONDS)
                lines.append(
                    f"• {d.name or d.id} (ID: {d.id})\n"
                    f"  Status: {st.upper()} | MCB: {d.mcb_watt} W\n"
                    f"  Terakhir aktif: {seen_str} WIB"
                )
            text = "\n".join(lines)
    await send_message_rate_limited(context.bot, update.effective_chat.id, text)


@allowlist_only
async def cmd_now(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with SessionLocal() as session:
        devices, err = _get_target_devices(session, context.args or [])
        if err:
            await send_message_rate_limited(context.bot, update.effective_chat.id, err)
            return

        lines = ["⚡ Status Listrik Real-Time:"]
        for d in devices:
            r = session.scalar(
                select(Reading)
                .where(Reading.device_id == d.id)
                .order_by(Reading.ts.desc())
                .limit(1)
            )
            if not r:
                lines.append(f"• {d.name or d.id}: Belum ada pembacaan telemetry.")
            else:
                lines.append(
                    f"• {d.name or d.id}:\n"
                    f"  Daya: {_format_id_number(r.p, 1)} W | "
                    f"Tegangan: {_format_id_number(r.v, 1)} V\n"
                    f"  Arus: {_format_id_number(r.i, 2)} A | "
                    f"PF: {_format_id_number(r.pf, 2)} | "
                    f"Freq: {_format_id_number(r.f, 1)} Hz\n"
                    f"  RSSI: {r.rssi} dBm | Waktu: {_format_time_wib(r.ts)} WIB"
                )
        text = "\n".join(lines)
    await send_message_rate_limited(context.bot, update.effective_chat.id, text)


@allowlist_only
async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with SessionLocal() as session:
        devices, err = _get_target_devices(session, context.args or [])
        if err:
            await send_message_rate_limited(context.bot, update.effective_chat.id, err)
            return

        lines = ["📊 Ringkasan Pemakaian Hari Ini:"]
        for d in devices:
            sum_data = calculate_device_summary(session, d.id, range="today")
            kwh_str = _format_id_number(sum_data["kwh"], 3)
            cost_str = _format_rupiah(sum_data["cost_rp"])
            peak_w_str = _format_id_number(sum_data["peak_w"], 1)
            peak_time = (
                _format_time_wib(sum_data["peak_ts"]) if sum_data.get("peak_ts") else "- WIB"
            )
            lines.append(
                f"• {d.name or d.id}:\n"
                f"  Energi: {kwh_str} kWh | Biaya: ±{cost_str}\n"
                f"  Beban Puncak: {peak_w_str} W (pukul {peak_time})"
            )
        text = "\n".join(lines)
    await send_message_rate_limited(context.bot, update.effective_chat.id, text)


@allowlist_only
async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with SessionLocal() as session:
        devices, err = _get_target_devices(session, context.args or [])
        if err:
            await send_message_rate_limited(context.bot, update.effective_chat.id, err)
            return

        lines = ["📅 Ringkasan Pemakaian Minggu Ini (Sejak Senin):"]
        for d in devices:
            sum_data = calculate_device_summary(session, d.id, range="week")
            kwh_str = _format_id_number(sum_data["kwh"], 3)
            cost_str = _format_rupiah(sum_data["cost_rp"])
            avg_w_str = _format_id_number(sum_data["avg_power_w"], 1)
            lines.append(
                f"• {d.name or d.id}:\n"
                f"  Energi: {kwh_str} kWh | Biaya: {cost_str}\n"
                f"  Daya Rata-rata: {avg_w_str} W"
            )
        text = "\n".join(lines)
    await send_message_rate_limited(context.bot, update.effective_chat.id, text)


@allowlist_only
async def cmd_month(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with SessionLocal() as session:
        devices, err = _get_target_devices(session, context.args or [])
        if err:
            await send_message_rate_limited(context.bot, update.effective_chat.id, err)
            return

        lines = ["🗓️ Ringkasan Pemakaian Bulan Ini:"]
        for d in devices:
            sum_data = calculate_device_summary(session, d.id, range="month")
            kwh_str = _format_id_number(sum_data["kwh"], 3)
            cost_str = _format_rupiah(sum_data["cost_rp"])
            peak_w_str = _format_id_number(sum_data["peak_w"], 1)
            lines.append(
                f"• {d.name or d.id}:\n"
                f"  Energi: {kwh_str} kWh | Biaya: {cost_str}\n"
                f"  Beban Puncak: {peak_w_str} W"
            )
        text = "\n".join(lines)
    await send_message_rate_limited(context.bot, update.effective_chat.id, text)


@allowlist_only
async def cmd_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with SessionLocal() as session:
        devices, err = _get_target_devices(session, context.args or [])
        if err:
            await send_message_rate_limited(context.bot, update.effective_chat.id, err)
            return

        lines = ["🔮 Proyeksi Tagihan Akhir Bulan:"]
        for d in devices:
            fc = calculate_device_forecast(session, d.id)
            if not fc.get("available"):
                lines.append(f"• {d.name or d.id}: Belum tersedia (data kurang dari 1 hari penuh).")
            else:
                cost_str = _format_rupiah(fc["projected_cost_rp"])
                kwh_str = _format_id_number(fc["projected_kwh"], 2)
                conf = " (perkiraan kasar)" if fc.get("low_confidence") else ""
                avg_daily_str = _format_id_number(fc["avg_daily_kwh"], 2)
                lines.append(
                    f"• {d.name or d.id}:\n"
                    f"  Perkiraan Tagihan: ±{cost_str} ({kwh_str} kWh){conf}\n"
                    f"  Dasar: {fc['basis_days']} hari penuh | "
                    f"Rata-rata: {avg_daily_str} kWh/hari"
                )
        text = "\n".join(lines)
    await send_message_rate_limited(context.bot, update.effective_chat.id, text)


@allowlist_only
async def cmd_anomali(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with SessionLocal() as session:
        devices, err = _get_target_devices(session, context.args or [])
        if err:
            await send_message_rate_limited(context.bot, update.effective_chat.id, err)
            return

        dev_ids = [d.id for d in devices]
        now_ts = int(time.time())
        from_ts = now_ts - (7 * 86400)

        anomalies = session.scalars(
            select(Anomaly)
            .where(Anomaly.device_id.in_(dev_ids), Anomaly.ts >= from_ts)
            .order_by(Anomaly.ts.desc())
            .limit(20)
        ).all()

        if not anomalies:
            text = "Tidak ada anomali dalam 7 hari terakhir."
        else:
            lines = ["🚨 Riwayat Peringatan & Anomali (7 Hari Terakhir, Terbaru Dulu):"]
            for a in anomalies:
                t_str = _format_datetime_wib(a.ts)
                lines.append(f"• [{a.severity.upper()}] {t_str} WIB:\n  {a.message}")
            text = "\n".join(lines)
    await send_message_rate_limited(context.bot, update.effective_chat.id, text)


@allowlist_only
async def cmd_tarif(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        text = "Format salah. Contoh: /tarif 1444.70 (maksimal 2 tempat desimal)"
        await send_message_rate_limited(context.bot, update.effective_chat.id, text)
        return

    raw_val = context.args[0].strip().replace(",", ".")
    try:
        dec_val = Decimal(raw_val)
        if dec_val <= 0:
            raise ValueError()
        # Tolak jika lebih dari 2 tempat desimal (konsisten dengan API)
        if dec_val.as_tuple().exponent < -2:
            raise ValueError()
        tariff_sen = int(round(dec_val * 100))
    except Exception:
        text = "Nilai tarif tidak valid. Contoh: /tarif 1444.70 (angka positif, maks 2 desimal)."
        await send_message_rate_limited(context.bot, update.effective_chat.id, text)
        return

    with SessionLocal() as session:
        setting = session.scalar(select(Setting).where(Setting.key == "tariff_sen_per_kwh"))
        if not setting:
            setting = Setting(key="tariff_sen_per_kwh", value=str(tariff_sen))
            session.add(setting)
        else:
            setting.value = str(tariff_sen)
        session.commit()

    text = f"✅ Tarif listrik berhasil diperbarui: Rp{dec_val:,.2f}/kWh (sen: {tariff_sen})."
    await send_message_rate_limited(context.bot, update.effective_chat.id, text)


@allowlist_only
async def cmd_batas(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        text = "Format salah. Contoh: /batas 2200 (angka watt batas daya)"
        await send_message_rate_limited(context.bot, update.effective_chat.id, text)
        return

    try:
        val = int(context.args[0].strip())
        if val < 100 or val > 100000:
            raise ValueError()
    except Exception:
        text = "Nilai batas daya tidak valid. Masukkan angka antara 100 s.d. 100000 Watt."
        await send_message_rate_limited(context.bot, update.effective_chat.id, text)
        return

    with SessionLocal() as session:
        setting = session.scalar(select(Setting).where(Setting.key == "power_limit_w"))
        if not setting:
            setting = Setting(key="power_limit_w", value=str(val))
            session.add(setting)
        else:
            setting.value = str(val)
        session.commit()

    text = f"✅ Batas daya peringatan berhasil diperbarui: {val} W."
    await send_message_rate_limited(context.bot, update.effective_chat.id, text)


@allowlist_only
async def cmd_laporan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        text = "Format salah. Gunakan: /laporan on atau /laporan off"
        await send_message_rate_limited(context.bot, update.effective_chat.id, text)
        return

    arg = context.args[0].strip().lower()
    if arg in ("on", "1", "true", "aktif"):
        val_str = "true"
        status_text = "diaktifkan"
    elif arg in ("off", "0", "false", "nonaktif"):
        val_str = "false"
        status_text = "dinonaktifkan"
    else:
        text = "Opsi tidak dikenal. Gunakan: /laporan on atau /laporan off"
        await send_message_rate_limited(context.bot, update.effective_chat.id, text)
        return

    with SessionLocal() as session:
        setting = session.scalar(select(Setting).where(Setting.key == "report_enabled"))
        if not setting:
            setting = Setting(key="report_enabled", value=val_str)
            session.add(setting)
        else:
            setting.value = val_str
        session.commit()

    text = f"✅ Laporan berkala otomatis berhasil {status_text}."
    await send_message_rate_limited(context.bot, update.effective_chat.id, text)


# ==============================================================================
# LIFECYCLE MANAGEMENT
# ==============================================================================

def register_handlers(app: Application) -> None:
    """Mendaftarkan seluruh CommandHandler ke bot application."""
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("perangkat", cmd_perangkat))
    app.add_handler(CommandHandler("now", cmd_now))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CommandHandler("month", cmd_month))
    app.add_handler(CommandHandler("forecast", cmd_forecast))
    app.add_handler(CommandHandler("anomali", cmd_anomali))
    app.add_handler(CommandHandler("tarif", cmd_tarif))
    app.add_handler(CommandHandler("batas", cmd_batas))
    app.add_handler(CommandHandler("laporan", cmd_laporan))


async def init_and_start_bot() -> None:
    """Menginisialisasi dan menjalankan polling Telegram Bot."""
    global _bot_app
    settings = get_settings()

    if not settings.is_bot_active or not settings.telegram_bot_token:
        logger.info("Telegram Bot tidak aktif (token kosong atau bot_enabled=False).")
        return

    try:
        app_builder = ApplicationBuilder().token(settings.telegram_bot_token)
        _bot_app = app_builder.build()

        register_handlers(_bot_app)

        await _bot_app.initialize()
        await _bot_app.start()
        if _bot_app.updater:
            await _bot_app.updater.start_polling()

        set_notification_sender(send_telegram_broadcast_sync)
        logger.info("Telegram Bot berhasil dimulai.")
    except Exception as err:
        safe_err = str(err)
        if settings.telegram_bot_token:
            safe_err = safe_err.replace(settings.telegram_bot_token, "[REDACTED]")
        logger.error(
            "Gagal menginisialisasi Telegram Bot: %s. Fallback ke default notifier.", safe_err
        )
        _bot_app = None


async def stop_bot() -> None:
    """Menghentikan bot dengan clean shutdown."""
    global _bot_app
    if _bot_app is not None:
        logger.info("Menghentikan Telegram Bot...")
        set_notification_sender(None)
        if _bot_app.updater and _bot_app.updater.running:
            await _bot_app.updater.stop()
        if _bot_app.running:
            await _bot_app.stop()
        await _bot_app.shutdown()
        _bot_app = None
        logger.info("Telegram Bot berhasil dihentikan.")
