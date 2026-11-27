import logging
from typing import Optional
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Setting
from app.services.alert import run_alert_check_job
from app.services.report_generator import (
    run_catchup_reports_job,
    run_daily_report_job,
    run_weekly_report_job,
)
from app.services.retention import run_retention_job
from app.services.timezone_utils import (
    DEFAULT_TIMEZONE_ID,
    get_timezone_short_label,
    normalize_timezone_name,
    resolve_zoneinfo,
)

logger = logging.getLogger(__name__)
TZ_WIB = ZoneInfo(DEFAULT_TIMEZONE_ID)

# Konfigurasi scheduler: 1 worker, coalesce=True, misfire_grace_time=3600s
scheduler = AsyncIOScheduler(
    timezone=TZ_WIB,
    job_defaults={
        "misfire_grace_time": 3600,
        "coalesce": True,
        "max_instances": 1,
    },
)


def _get_setting_report_schedule() -> tuple[int, str]:
    hour_val = 21
    tz_val = DEFAULT_TIMEZONE_ID
    try:
        with SessionLocal() as session:
            raw_hour = session.scalar(select(Setting.value).where(Setting.key == "report_hour"))
            if raw_hour is not None:
                hour_val = int(raw_hour)
            raw_tz = session.scalar(select(Setting.value).where(Setting.key == "report_timezone"))
            if raw_tz:
                tz_val = normalize_timezone_name(raw_tz)
    except Exception as err:
        logger.warning("Could not read report schedule from DB: %s", err)
    return hour_val, tz_val


def _get_setting_report_hour() -> int:
    hour_val, _ = _get_setting_report_schedule()
    return hour_val


def reschedule_daily_report(
    new_hour: Optional[int] = None,
    timezone_name: Optional[str] = None,
) -> None:
    """Memperbarui jadwal laporan harian & mingguan sesuai jam dan zona waktu (WIB/WITA/WIT)."""
    if not scheduler.running:
        return
    db_hour, db_tz = _get_setting_report_schedule()
    target_hour = db_hour if new_hour is None else int(new_hour)
    target_tz = normalize_timezone_name(timezone_name or db_tz)
    zone_obj = resolve_zoneinfo(target_tz)

    daily_job = scheduler.get_job("daily_report_job")
    if daily_job:
        scheduler.reschedule_job(
            "daily_report_job",
            trigger=CronTrigger(hour=target_hour, minute=0, timezone=zone_obj),
        )
        logger.info(
            "Rescheduled daily_report_job to %02d:00 %s (%s)",
            target_hour,
            get_timezone_short_label(target_tz),
            target_tz,
        )

    weekly_job = scheduler.get_job("weekly_report_job")
    if weekly_job:
        scheduler.reschedule_job(
            "weekly_report_job",
            trigger=CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=zone_obj),
        )


def init_scheduler_jobs(
    report_hour: Optional[int] = None,
    report_timezone: Optional[str] = None,
) -> None:
    """Mendaftarkan seluruh background job terjadwal."""
    db_hour, db_tz = _get_setting_report_schedule()
    if report_hour is None:
        report_hour = db_hour
    tz_name = normalize_timezone_name(report_timezone or db_tz)
    report_tz = resolve_zoneinfo(tz_name)

    # 1. Job Alert L1: dievaluasi tiap 15 detik dari jendela readings (bukan jalur ingest)
    if not scheduler.get_job("alert_l1_job"):
        scheduler.add_job(
            run_alert_check_job,
            trigger=IntervalTrigger(seconds=15, timezone=TZ_WIB),
            id="alert_l1_job",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    # 2. Job Retensi Database: dijalankan tiap hari jam 03.00 WIB
    if not scheduler.get_job("retention_job"):
        scheduler.add_job(
            run_retention_job,
            trigger=CronTrigger(hour=3, minute=0, timezone=TZ_WIB),
            id="retention_job",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    # 3. Job Laporan Harian: mengikuti report_hour & report_timezone pengguna/operator
    if not scheduler.get_job("daily_report_job"):
        scheduler.add_job(
            run_daily_report_job,
            trigger=CronTrigger(hour=report_hour, minute=0, timezone=report_tz),
            id="daily_report_job",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    # 4. Job Laporan Mingguan: mengikuti zona waktu pengaturan aktif
    if not scheduler.get_job("weekly_report_job"):
        scheduler.add_job(
            run_weekly_report_job,
            trigger=CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=report_tz),
            id="weekly_report_job",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    # 5. Job Catch-up Laporan Terlewat: diperiksa tiap 60 detik (dan saat startup)
    if not scheduler.get_job("catchup_reports_job"):
        scheduler.add_job(
            run_catchup_reports_job,
            trigger=IntervalTrigger(seconds=60, timezone=TZ_WIB),
            id="catchup_reports_job",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )


def start_scheduler() -> bool:
    """Memulai scheduler jika aktif sesuai konfigurasi (otomatis mati jika APP_ENV=test)."""
    settings = get_settings()
    if not settings.is_scheduler_active:
        logger.info("Scheduler is disabled (app_env=%s, scheduler_enabled=%s).",
                    settings.app_env, settings.scheduler_enabled)
        return False

    if not scheduler.running:
        init_scheduler_jobs()
        scheduler.start()
        jobs = [f"{j.id} ({j.trigger})" for j in scheduler.get_jobs()]
        logger.info("APScheduler aktif. Jobs terdaftar: %s", jobs)
        return True
    return False


def stop_scheduler() -> None:
    """Menghentikan scheduler secara aman."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped.")
