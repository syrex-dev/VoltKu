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

logger = logging.getLogger(__name__)
TZ_WIB = ZoneInfo("Asia/Jakarta")

# Konfigurasi scheduler: Asia/Jakarta, 1 worker, coalesce=True, misfire_grace_time=3600s
scheduler = AsyncIOScheduler(
    timezone=TZ_WIB,
    job_defaults={
        "misfire_grace_time": 3600,
        "coalesce": True,
        "max_instances": 1,
    },
)


def _get_setting_report_hour() -> int:
    try:
        with SessionLocal() as session:
            val = session.scalar(select(Setting.value).where(Setting.key == "report_hour"))
            if val is not None:
                return int(val)
    except Exception as err:
        logger.warning("Could not read report_hour from DB: %s", err)
    return 21


def reschedule_daily_report(new_hour: int) -> None:
    """Memperbarui jadwal laporan harian sesuai nilai baru settings.report_hour."""
    if not scheduler.running:
        return
    job = scheduler.get_job("daily_report_job")
    if job:
        trigger = CronTrigger(hour=new_hour, minute=0, timezone=TZ_WIB)
        scheduler.reschedule_job("daily_report_job", trigger=trigger)
        logger.info("Rescheduled daily_report_job to %02d:00 WIB", new_hour)


def init_scheduler_jobs(report_hour: Optional[int] = None) -> None:
    """Mendaftarkan seluruh background job terjadwal."""
    if report_hour is None:
        report_hour = _get_setting_report_hour()

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

    # 3. Job Laporan Harian: mengikuti settings.report_hour (misal 21.00 WIB)
    if not scheduler.get_job("daily_report_job"):
        scheduler.add_job(
            run_daily_report_job,
            trigger=CronTrigger(hour=report_hour, minute=0, timezone=TZ_WIB),
            id="daily_report_job",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    # 4. Job Laporan Mingguan: dijalankan tiap Minggu jam 20.00 WIB
    if not scheduler.get_job("weekly_report_job"):
        scheduler.add_job(
            run_weekly_report_job,
            trigger=CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=TZ_WIB),
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
