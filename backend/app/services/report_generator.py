import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import Device, ScheduledReportsLog, Setting
from app.services.notifier import is_channel_configured, send_alert_notification
from app.services.reports import calculate_device_forecast, calculate_device_summary
from app.services.timezone_utils import (
    DEFAULT_TIMEZONE_ID,
    get_timezone_short_label,
    normalize_timezone_name,
    resolve_zoneinfo,
)

logger = logging.getLogger(__name__)
TZ_WIB = ZoneInfo(DEFAULT_TIMEZONE_ID)


def _get_report_timezone(session: Session) -> str:
    val = session.scalar(select(Setting.value).where(Setting.key == "report_timezone"))
    return normalize_timezone_name(val)


def _format_id_number(val: float, decimals: int = 3) -> str:
    """Format angka dengan koma sebagai pemisah desimal dan titik sebagai pemisah ribuan."""
    fmt_str = f"{{:,.{decimals}f}}"
    formatted = fmt_str.format(val)
    # Ubah format Inggris (1,234.567) ke format Indonesia (1.234,567)
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def _format_rupiah(rp: int) -> str:
    """Format Rupiah dengan pemisah ribuan titik (contoh: Rp12.185)."""
    return f"Rp{rp:,}".replace(",", ".")


def is_report_enabled(session: Session) -> bool:
    val = session.scalar(select(Setting.value).where(Setting.key == "report_enabled"))
    if val is not None:
        return val.strip().lower() in ("true", "1", "yes", "on")
    return True


def generate_and_send_daily_report(
    session: Session,
    target_date_str: Optional[str] = None,
    force: bool = False,
    now_ts: Optional[int] = None,
) -> bool:
    """Membuat dan mengirimkan laporan harian otomatis.

    - Target date default: hari ini WIB.
    - Idempotensi: periksa scheduled_reports_log.
    - Ditulis ke log HANYA jika pengiriman sukses.
    """
    if not is_channel_configured():
        logger.info("Daily report skipped: no notification channel configured.")
        return False

    if not is_report_enabled(session):
        logger.info("Daily report skipped: report_enabled is False in settings.")
        return False

    tz_name = _get_report_timezone(session)
    report_tz = resolve_zoneinfo(tz_name)
    tz_short = get_timezone_short_label(tz_name)

    now_dt = (
        datetime.fromtimestamp(now_ts, tz=report_tz)
        if now_ts is not None
        else datetime.now(report_tz)
    )
    if target_date_str is None:
        target_date_str = now_dt.strftime("%Y-%m-%d")

    # Cek idempotensi
    existing_log = session.scalar(
        select(ScheduledReportsLog).where(
            ScheduledReportsLog.report_type == "daily",
            ScheduledReportsLog.report_date == target_date_str,
        )
    )
    if existing_log and not force:
        logger.info(
            "Daily report for %s already sent at %s. Skipping.",
            target_date_str,
            existing_log.sent_at,
        )
        return False

    settings = get_settings()
    exclude_prefixes = [
        p.strip() for p in settings.alert_exclude_device_prefixes.split(",") if p.strip()
    ]

    devices = session.scalars(select(Device)).all()
    # Filter perangkat (hanya perangkat non-sim; jangan kirim laporan kosong jika tidak ada)
    eligible_devices = [d for d in devices if not any(d.id.startswith(p) for p in exclude_prefixes)]

    if not eligible_devices:
        logger.info("Daily report skipped: no non-sim devices found to report.")
        return False

    # Bangun pesan laporan harian
    reports_sent = 0
    t_date = datetime.strptime(target_date_str, "%Y-%m-%d").replace(tzinfo=report_tz)
    date_formatted = t_date.strftime("%d %b %Y")

    for dev in eligible_devices:
        # Ringkasan pemakaian hari ini
        summary = calculate_device_summary(
            session=session,
            device_id=dev.id,
            range="today",
            now_dt=now_dt,
        )
        forecast = calculate_device_forecast(
            session=session,
            device_id=dev.id,
            now_dt=now_dt,
        )

        kwh_str = _format_id_number(summary["kwh"], 3)
        cost_str = _format_rupiah(summary["cost_rp"])

        peak_w_str = _format_id_number(summary["peak_w"], 1)
        if summary.get("peak_ts"):
            peak_dt = datetime.fromtimestamp(summary["peak_ts"], tz=report_tz)
            peak_time_str = peak_dt.strftime(f"%H.%M {tz_short}")
        else:
            peak_time_str = f"- {tz_short}"

        if forecast.get("available"):
            cost_proj = _format_rupiah(forecast["projected_cost_rp"])
            proj_str = f"±{cost_proj} (Basis {forecast['basis_days']} Hari)"
        else:
            proj_str = "Belum cukup data"

        msg_lines = [
            f"Laporan {date_formatted} ({dev.name})",
            f"Pemakaian: {kwh_str} kWh | Biaya: ±{cost_str}",
            f"Puncak: {peak_w_str} W pukul {peak_time_str}",
            f"Proyeksi bulan ini: {proj_str}",
            "Catatan: sistem beroperasi normal.",
        ]
        message = "\n".join(msg_lines)

        # Kirim notifikasi dengan event_key dedup
        evt_key = f"report:{dev.id}:daily:{target_date_str}"
        if send_alert_notification(message, event_key=evt_key):
            reports_sent += 1

    # Catat idempotensi HANYA jika minimal satu laporan terkirim sukses
    if reports_sent > 0:
        sent_epoch = int(now_dt.timestamp())
        if not existing_log:
            session.add(
                ScheduledReportsLog(
                    report_type="daily",
                    report_date=target_date_str,
                    sent_at=sent_epoch,
                )
            )
        else:
            existing_log.sent_at = sent_epoch
        session.commit()
        logger.info("Daily report for %s recorded in scheduled_reports_log.", target_date_str)
        return True

    return False


def generate_and_send_weekly_report(
    session: Session,
    target_date_str: Optional[str] = None,
    force: bool = False,
    now_ts: Optional[int] = None,
) -> bool:
    """Membuat dan mengirimkan laporan mingguan otomatis (tiap Minggu 20.00 WIB)."""
    if not is_channel_configured():
        logger.info("Weekly report skipped: no notification channel configured.")
        return False

    if not is_report_enabled(session):
        logger.info("Weekly report skipped: report_enabled is False in settings.")
        return False

    tz_name = _get_report_timezone(session)
    report_tz = resolve_zoneinfo(tz_name)

    now_dt = (
        datetime.fromtimestamp(now_ts, tz=report_tz)
        if now_ts is not None
        else datetime.now(report_tz)
    )
    if target_date_str is None:
        target_date_str = now_dt.strftime("%Y-%m-%d")

    # Cek idempotensi
    existing_log = session.scalar(
        select(ScheduledReportsLog).where(
            ScheduledReportsLog.report_type == "weekly",
            ScheduledReportsLog.report_date == target_date_str,
        )
    )
    if existing_log and not force:
        logger.info("Weekly report for %s already sent. Skipping.", target_date_str)
        return False

    settings = get_settings()
    exclude_prefixes = [
        p.strip() for p in settings.alert_exclude_device_prefixes.split(",") if p.strip()
    ]

    devices = session.scalars(select(Device)).all()
    eligible_devices = [d for d in devices if not any(d.id.startswith(p) for p in exclude_prefixes)]

    if not eligible_devices:
        logger.info("Weekly report skipped: no non-sim devices found to report.")
        return False

    reports_sent = 0
    t_date = datetime.strptime(target_date_str, "%Y-%m-%d").replace(tzinfo=report_tz)
    # Rentang 7 hari terakhir (Senin s.d. Minggu)
    start_week = t_date - timedelta(days=6)
    range_label = f"{start_week.strftime('%d %b')} - {t_date.strftime('%d %b %Y')}"

    for dev in eligible_devices:
        summary = calculate_device_summary(
            session=session,
            device_id=dev.id,
            range="week",
            now_dt=now_dt,
        )

        kwh_str = _format_id_number(summary["kwh"], 3)
        cost_str = _format_rupiah(summary["cost_rp"])
        avg_daily_kwh = _format_id_number(summary["kwh"] / 7.0, 3)

        msg_lines = [
            f"Laporan Mingguan {range_label} ({dev.name})",
            f"Pemakaian: {kwh_str} kWh | Biaya: ±{cost_str}",
            f"Rata-rata harian: {avg_daily_kwh} kWh/hari",
            "Catatan: rekapitulasi konsumsi mingguan selesai.",
        ]
        message = "\n".join(msg_lines)

        evt_key = f"report:{dev.id}:weekly:{target_date_str}"
        if send_alert_notification(message, event_key=evt_key):
            reports_sent += 1

    if reports_sent > 0:
        sent_epoch = int(now_dt.timestamp())
        if not existing_log:
            session.add(
                ScheduledReportsLog(
                    report_type="weekly",
                    report_date=target_date_str,
                    sent_at=sent_epoch,
                )
            )
        else:
            existing_log.sent_at = sent_epoch
        session.commit()
        return True

    return False


async def run_daily_report_job(
    target_date_str: Optional[str] = None,
    force: bool = False,
    now_ts: Optional[int] = None,
) -> bool:
    """Menjalankan generator laporan harian secara asinkron via to_thread."""
    def _sync():
        with SessionLocal() as session:
            return generate_and_send_daily_report(
                session, target_date_str=target_date_str, force=force, now_ts=now_ts
            )

    return await asyncio.to_thread(_sync)


async def run_weekly_report_job(
    target_date_str: Optional[str] = None,
    force: bool = False,
    now_ts: Optional[int] = None,
) -> bool:
    """Menjalankan generator laporan mingguan secara asinkron via to_thread."""
    def _sync():
        with SessionLocal() as session:
            return generate_and_send_weekly_report(
                session, target_date_str=target_date_str, force=force, now_ts=now_ts
            )

    return await asyncio.to_thread(_sync)


def check_and_send_catchup_reports(
    session: Session,
    now_dt: Optional[datetime] = None,
) -> list[str]:
    """Memeriksa dan mengirimkan laporan yang terlewat (catch-up).

    Aturan:
    1. Laporan harian: jika sekarang >= report_hour (WIB) dan belum ada catatan untuk hari itu,
       kirim (sampai 23.59 WIB hari yang sama; laporan hari kemarin tidak dikirim ulang).
    2. Laporan mingguan: jika hari ini Minggu (weekday 6) dan jam >= 20 dan belum ada catatan
       untuk minggu itu, kirim (sampai 23.59 WIB hari Minggu).
    """
    if not is_channel_configured():
        return []

    if not is_report_enabled(session):
        return []

    tz_name = _get_report_timezone(session)
    report_tz = resolve_zoneinfo(tz_name)
    now_local = now_dt.astimezone(report_tz) if now_dt is not None else datetime.now(report_tz)
    today_str = now_local.strftime("%Y-%m-%d")
    now_ts = int(now_local.timestamp())
    actions: list[str] = []

    # 1. Catch-up harian
    report_hour_setting = session.scalar(select(Setting.value).where(Setting.key == "report_hour"))
    report_hour = int(report_hour_setting) if report_hour_setting else 21

    if now_local.hour >= report_hour:
        sent_daily = session.scalar(
            select(ScheduledReportsLog).where(
                ScheduledReportsLog.report_type == "daily",
                ScheduledReportsLog.report_date == today_str,
            )
        )
        if not sent_daily:
            success = generate_and_send_daily_report(
                session, target_date_str=today_str, force=False, now_ts=now_ts
            )
            if success:
                actions.append(f"catchup_daily_{today_str}")

    # 2. Catch-up mingguan: hanya di hari Minggu (weekday == 6) jam >= 20
    if now_local.weekday() == 6 and now_local.hour >= 20:
        sent_weekly = session.scalar(
            select(ScheduledReportsLog).where(
                ScheduledReportsLog.report_type == "weekly",
                ScheduledReportsLog.report_date == today_str,
            )
        )
        if not sent_weekly:
            success = generate_and_send_weekly_report(
                session, target_date_str=today_str, force=False, now_ts=now_ts
            )
            if success:
                actions.append(f"catchup_weekly_{today_str}")

    return actions


async def run_catchup_reports_job(now_dt: Optional[datetime] = None) -> list[str]:
    """Menjalankan pengecekan catch-up laporan secara asinkron via to_thread."""
    def _sync():
        with SessionLocal() as session:
            return check_and_send_catchup_reports(session, now_dt=now_dt)

    return await asyncio.to_thread(_sync)
