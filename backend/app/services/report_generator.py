import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import Device, ScheduledReportsLog, Setting, UserSetting
from app.services.notifier import is_channel_configured, send_alert_notification
from app.services.push_notifier import notify_device_owner
from app.services.reports import calculate_device_forecast, calculate_device_summary
from app.services.timezone_utils import (
    DEFAULT_TIMEZONE_ID,
    get_timezone_short_label,
    normalize_timezone_name,
    resolve_zoneinfo,
)

logger = logging.getLogger(__name__)
TZ_WIB = ZoneInfo(DEFAULT_TIMEZONE_ID)


def _get_effective_setting(
    session: Session, key: str, user_id: Optional[int] = None
) -> Optional[str]:
    if user_id is not None:
        u_val = session.scalar(
            select(UserSetting.value).where(UserSetting.user_id == user_id, UserSetting.key == key)
        )
        if u_val is not None:
            return u_val
    return session.scalar(select(Setting.value).where(Setting.key == key))


def _get_report_timezone(session: Session, user_id: Optional[int] = None) -> str:
    val = _get_effective_setting(session, "report_timezone", user_id=user_id)
    return normalize_timezone_name(val)


def _get_report_hour(session: Session, user_id: Optional[int] = None) -> int:
    val = _get_effective_setting(session, "report_hour", user_id=user_id)
    if val is not None:
        try:
            return max(0, min(23, int(val)))
        except ValueError:
            pass
    return 21


def _format_id_number(val: float, decimals: int = 3) -> str:
    """Format angka dengan koma sebagai pemisah desimal dan titik sebagai pemisah ribuan."""
    fmt_str = f"{{:,.{decimals}f}}"
    formatted = fmt_str.format(val)
    # Ubah format Inggris (1,234.567) ke format Indonesia (1.234,567)
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def _format_rupiah(rp: int) -> str:
    """Format Rupiah dengan pemisah ribuan titik (contoh: Rp12.185)."""
    return f"Rp{rp:,}".replace(",", ".")


def is_report_enabled(session: Session, user_id: Optional[int] = None) -> bool:
    val = _get_effective_setting(session, "report_enabled", user_id=user_id)
    if val is not None:
        return val.strip().lower() in ("true", "1", "yes", "on")
    return True


def _get_eligible_devices(
    session: Session,
    *,
    owner_user_id: Optional[int] = None,
    only_unowned: bool = False,
) -> list[Device]:
    settings = get_settings()
    exclude_prefixes = [
        p.strip() for p in settings.alert_exclude_device_prefixes.split(",") if p.strip()
    ]
    stmt = select(Device)
    if owner_user_id is not None:
        stmt = stmt.where(Device.owner_user_id == owner_user_id)
    elif only_unowned:
        stmt = stmt.where(Device.owner_user_id.is_(None))
    devices = session.scalars(stmt).all()
    return [d for d in devices if not any(d.id.startswith(p) for p in exclude_prefixes)]


def _deliver_device_report(
    session: Session,
    *,
    dev: Device,
    title: str,
    message: str,
    report_kind: str,
    target_date_str: str,
    now_ts: int,
) -> bool:
    """Kirim rekap via channel global (bila aktif) dan inbox/FCM push pemilik perangkat."""
    evt_key = f"report:{dev.id}:{report_kind}:{target_date_str}"
    delivered = False

    if is_channel_configured():
        if send_alert_notification(message, event_key=evt_key):
            delivered = True

    if getattr(dev, "owner_user_id", None) is not None:
        try:
            notif = notify_device_owner(
                session,
                device=dev,
                title=title,
                body=message,
                category="report",
                severity="info",
                data={"report_type": report_kind, "report_date": target_date_str},
                event_key=evt_key,
                now_ts=now_ts,
            )
            if notif is not None:
                delivered = True
        except Exception as exc:
            logger.debug("Push notif report %s gagal untuk %s: %s", report_kind, dev.id, exc)

    return delivered


def generate_and_send_daily_report(
    session: Session,
    target_date_str: Optional[str] = None,
    force: bool = False,
    now_ts: Optional[int] = None,
    *,
    owner_user_id: Optional[int] = None,
    only_unowned: bool = False,
    tz_name_override: Optional[str] = None,
    log_report_type: str = "daily",
) -> bool:
    """Membuat dan mengirimkan laporan harian otomatis (global atau per tenant)."""
    if not is_report_enabled(session, user_id=owner_user_id):
        logger.info("Daily report skipped: report_enabled is False in settings.")
        return False

    eligible_devices = _get_eligible_devices(
        session, owner_user_id=owner_user_id, only_unowned=only_unowned
    )
    if not eligible_devices:
        logger.info("Daily report skipped: no eligible non-sim devices found.")
        return False

    has_global_channel = is_channel_configured()
    has_tenant_targets = any(
        getattr(d, "owner_user_id", None) is not None for d in eligible_devices
    )
    if not has_global_channel and not has_tenant_targets:
        logger.info("Daily report skipped: no notification channel configured.")
        return False

    tz_name = normalize_timezone_name(
        tz_name_override or _get_report_timezone(session, user_id=owner_user_id)
    )
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
            ScheduledReportsLog.report_type == log_report_type,
            ScheduledReportsLog.report_date == target_date_str,
        )
    )
    if existing_log and not force:
        logger.info(
            "Daily report (%s) for %s already sent at %s. Skipping.",
            log_report_type,
            target_date_str,
            existing_log.sent_at,
        )
        return False

    # Bangun & kirim laporan harian
    reports_sent = 0
    t_date = datetime.strptime(target_date_str, "%Y-%m-%d").replace(tzinfo=report_tz)
    date_formatted = t_date.strftime("%d %b %Y")
    sent_epoch = int(now_dt.timestamp())

    for dev in eligible_devices:
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
        title = f"Rekap Harian {date_formatted} · {dev.name}"

        if _deliver_device_report(
            session,
            dev=dev,
            title=title,
            message=message,
            report_kind="daily",
            target_date_str=target_date_str,
            now_ts=sent_epoch,
        ):
            reports_sent += 1

    # Catat idempotensi HANYA jika minimal satu laporan terkirim sukses
    if reports_sent > 0:
        if not existing_log:
            session.add(
                ScheduledReportsLog(
                    report_type=log_report_type,
                    report_date=target_date_str,
                    sent_at=sent_epoch,
                )
            )
        else:
            existing_log.sent_at = sent_epoch
        session.commit()
        logger.info(
            "Daily report (%s) for %s recorded in scheduled_reports_log.",
            log_report_type,
            target_date_str,
        )
        return True

    return False


def generate_and_send_weekly_report(
    session: Session,
    target_date_str: Optional[str] = None,
    force: bool = False,
    now_ts: Optional[int] = None,
    *,
    owner_user_id: Optional[int] = None,
    only_unowned: bool = False,
    tz_name_override: Optional[str] = None,
    log_report_type: str = "weekly",
) -> bool:
    """Membuat dan mengirimkan laporan mingguan otomatis (global atau per tenant)."""
    if not is_report_enabled(session, user_id=owner_user_id):
        logger.info("Weekly report skipped: report_enabled is False in settings.")
        return False

    eligible_devices = _get_eligible_devices(
        session, owner_user_id=owner_user_id, only_unowned=only_unowned
    )
    if not eligible_devices:
        logger.info("Weekly report skipped: no eligible non-sim devices found.")
        return False

    has_global_channel = is_channel_configured()
    has_tenant_targets = any(
        getattr(d, "owner_user_id", None) is not None for d in eligible_devices
    )
    if not has_global_channel and not has_tenant_targets:
        logger.info("Weekly report skipped: no notification channel configured.")
        return False

    tz_name = normalize_timezone_name(
        tz_name_override or _get_report_timezone(session, user_id=owner_user_id)
    )
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
            ScheduledReportsLog.report_type == log_report_type,
            ScheduledReportsLog.report_date == target_date_str,
        )
    )
    if existing_log and not force:
        logger.info(
            "Weekly report (%s) for %s already sent. Skipping.",
            log_report_type,
            target_date_str,
        )
        return False

    reports_sent = 0
    t_date = datetime.strptime(target_date_str, "%Y-%m-%d").replace(tzinfo=report_tz)
    start_week = t_date - timedelta(days=6)
    range_label = f"{start_week.strftime('%d %b')} - {t_date.strftime('%d %b %Y')}"
    sent_epoch = int(now_dt.timestamp())

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
        title = f"Rekap Mingguan · {dev.name}"

        if _deliver_device_report(
            session,
            dev=dev,
            title=title,
            message=message,
            report_kind="weekly",
            target_date_str=target_date_str,
            now_ts=sent_epoch,
        ):
            reports_sent += 1

    if reports_sent > 0:
        if not existing_log:
            session.add(
                ScheduledReportsLog(
                    report_type=log_report_type,
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
    """Menjalankan generator laporan harian global secara asinkron via to_thread."""
    def _sync():
        with SessionLocal() as session:
            return generate_and_send_daily_report(
                session,
                target_date_str=target_date_str,
                force=force,
                now_ts=now_ts,
                only_unowned=(target_date_str is None and not force),
            )

    return await asyncio.to_thread(_sync)


async def run_weekly_report_job(
    target_date_str: Optional[str] = None,
    force: bool = False,
    now_ts: Optional[int] = None,
) -> bool:
    """Menjalankan generator laporan mingguan global secara asinkron via to_thread."""
    def _sync():
        with SessionLocal() as session:
            return generate_and_send_weekly_report(
                session,
                target_date_str=target_date_str,
                force=force,
                now_ts=now_ts,
                only_unowned=(target_date_str is None and not force),
            )

    return await asyncio.to_thread(_sync)


def check_and_send_catchup_reports(
    session: Session,
    now_dt: Optional[datetime] = None,
) -> list[str]:
    """Memeriksa dan mengirimkan laporan terjadwal & catch-up lintas tenant dan zona waktu.

    1. Perangkat global / tanpa pemilik (owner_user_id IS NULL): mengikuti Setting global.
    2. Perangkat milik tenant (owner_user_id IS NOT NULL): mengikuti UserSetting masing-masing
       (report_enabled, report_hour, report_timezone WIB/WITA/WIT) serta mengirim ke Inbox/Push.
    """
    actions: list[str] = []

    # 1. Global / Unowned devices
    if is_channel_configured() and is_report_enabled(session):
        tz_name = _get_report_timezone(session)
        report_tz = resolve_zoneinfo(tz_name)
        now_local = now_dt.astimezone(report_tz) if now_dt is not None else datetime.now(report_tz)
        today_str = now_local.strftime("%Y-%m-%d")
        now_ts = int(now_local.timestamp())
        report_hour = _get_report_hour(session)

        if now_local.hour >= report_hour:
            sent_daily = session.scalar(
                select(ScheduledReportsLog).where(
                    ScheduledReportsLog.report_type == "daily",
                    ScheduledReportsLog.report_date == today_str,
                )
            )
            if not sent_daily:
                success = generate_and_send_daily_report(
                    session,
                    target_date_str=today_str,
                    force=False,
                    now_ts=now_ts,
                    only_unowned=True,
                    log_report_type="daily",
                )
                if success:
                    actions.append(f"catchup_daily_{today_str}")

        if now_local.weekday() == 6 and now_local.hour >= 20:
            sent_weekly = session.scalar(
                select(ScheduledReportsLog).where(
                    ScheduledReportsLog.report_type == "weekly",
                    ScheduledReportsLog.report_date == today_str,
                )
            )
            if not sent_weekly:
                success = generate_and_send_weekly_report(
                    session,
                    target_date_str=today_str,
                    force=False,
                    now_ts=now_ts,
                    only_unowned=True,
                    log_report_type="weekly",
                )
                if success:
                    actions.append(f"catchup_weekly_{today_str}")

    # 2. Per-Tenant owned devices (masing-masing WIB / WITA / WIT & jam rekap user)
    all_eligible = _get_eligible_devices(session)
    tenant_ids = sorted(
        {
            int(d.owner_user_id)
            for d in all_eligible
            if getattr(d, "owner_user_id", None) is not None
        }
    )
    for uid in tenant_ids:
        if not is_report_enabled(session, user_id=uid):
            continue
        u_tz_name = _get_report_timezone(session, user_id=uid)
        u_tz = resolve_zoneinfo(u_tz_name)
        u_local = now_dt.astimezone(u_tz) if now_dt is not None else datetime.now(u_tz)
        u_today_str = u_local.strftime("%Y-%m-%d")
        u_now_ts = int(u_local.timestamp())
        u_hour = _get_report_hour(session, user_id=uid)

        daily_key = f"u{uid}:d"
        if u_local.hour >= u_hour:
            sent_u_daily = session.scalar(
                select(ScheduledReportsLog).where(
                    ScheduledReportsLog.report_type == daily_key,
                    ScheduledReportsLog.report_date == u_today_str,
                )
            )
            if not sent_u_daily:
                ok_d = generate_and_send_daily_report(
                    session,
                    target_date_str=u_today_str,
                    force=False,
                    now_ts=u_now_ts,
                    owner_user_id=uid,
                    tz_name_override=u_tz_name,
                    log_report_type=daily_key,
                )
                if ok_d:
                    actions.append(f"tenant_{uid}_daily_{u_today_str}")

        weekly_key = f"u{uid}:w"
        if u_local.weekday() == 6 and u_local.hour >= 20:
            sent_u_weekly = session.scalar(
                select(ScheduledReportsLog).where(
                    ScheduledReportsLog.report_type == weekly_key,
                    ScheduledReportsLog.report_date == u_today_str,
                )
            )
            if not sent_u_weekly:
                ok_w = generate_and_send_weekly_report(
                    session,
                    target_date_str=u_today_str,
                    force=False,
                    now_ts=u_now_ts,
                    owner_user_id=uid,
                    tz_name_override=u_tz_name,
                    log_report_type=weekly_key,
                )
                if ok_w:
                    actions.append(f"tenant_{uid}_weekly_{u_today_str}")

    return actions


async def run_catchup_reports_job(now_dt: Optional[datetime] = None) -> list[str]:
    """Menjalankan pengecekan catch-up laporan secara asinkron via to_thread."""
    def _sync():
        with SessionLocal() as session:
            return check_and_send_catchup_reports(session, now_dt=now_dt)

    return await asyncio.to_thread(_sync)
