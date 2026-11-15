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
from app.services.notifier import send_alert_notification
from app.services.reports import calculate_device_forecast, calculate_device_summary

logger = logging.getLogger(__name__)
TZ_WIB = ZoneInfo("Asia/Jakarta")


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
    if not is_report_enabled(session):
        logger.info("Daily report skipped: report_enabled is False in settings.")
        return False

    now_dt = (
        datetime.fromtimestamp(now_ts, tz=TZ_WIB)
        if now_ts is not None
        else datetime.now(TZ_WIB)
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
    # Filter perangkat (jika ada non-sim gunakan non-sim, jika tidak ada kirim perangkat yang ada)
    eligible_devices = [d for d in devices if not any(d.id.startswith(p) for p in exclude_prefixes)]
    if not eligible_devices:
        eligible_devices = devices

    if not eligible_devices:
        logger.warning("Daily report: no devices found to report.")
        return False

    # Bangun pesan laporan harian
    reports_sent = 0
    t_date = datetime.strptime(target_date_str, "%Y-%m-%d").replace(tzinfo=TZ_WIB)
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
            peak_dt = datetime.fromtimestamp(summary["peak_ts"], tz=TZ_WIB)
            peak_time_str = peak_dt.strftime("%H.%M WIB")
        else:
            peak_time_str = "- WIB"

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

        # Kirim notifikasi
        if send_alert_notification(message):
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
    if not is_report_enabled(session):
        logger.info("Weekly report skipped: report_enabled is False in settings.")
        return False

    now_dt = (
        datetime.fromtimestamp(now_ts, tz=TZ_WIB)
        if now_ts is not None
        else datetime.now(TZ_WIB)
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
        eligible_devices = devices

    if not eligible_devices:
        return False

    reports_sent = 0
    t_date = datetime.strptime(target_date_str, "%Y-%m-%d").replace(tzinfo=TZ_WIB)
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

        if send_alert_notification(message):
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
