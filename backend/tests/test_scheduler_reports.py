from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from app.config import Settings
from app.models import Base, DailyStat, Device, Reading, ScheduledReportsLog, Setting
from app.mqtt_ingest import process_telemetry_payload
from app.services.notifier import set_notification_sender
from app.services.report_generator import (
    generate_and_send_daily_report,
    generate_and_send_weekly_report,
)
from app.services.scheduler import init_scheduler_jobs, reschedule_daily_report, scheduler
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

TZ_WIB = ZoneInfo("Asia/Jakarta")


def get_test_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    session.add(Setting(key="tariff_sen_per_kwh", value="144470"))
    session.add(Setting(key="extra_percent", value="0.0"))
    session.add(Setting(key="report_hour", value="21"))
    session.add(Setting(key="report_enabled", value="true"))
    session.commit()
    return engine, session


def test_daily_report_generation_and_idempotency():
    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)

    sim_dt = datetime(2026, 11, 20, 21, 0, 0, tzinfo=TZ_WIB)
    now_ts = int(sim_dt.timestamp())

    session.add(
        Device(id="demo-1", name="Warung Demo", mcb_watt=2200, last_seen_at=now_ts, status="online")
    )
    # Tambahkan pembacaan hari ini
    today_start = int(datetime(2026, 11, 20, 0, 0, 0, tzinfo=TZ_WIB).timestamp())
    session.add(
        Reading(
            device_id="demo-1",
            ts=today_start + 3600,
            v=220.0,
            i=5.0,
            p=1100.0,
            e_kwh=10.0,
            delta_kwh=3.5,
            f=50.0,
            pf=1.0,
            rssi=-60,
        )
    )
    session.commit()

    # Kirim laporan pertama
    res1 = generate_and_send_daily_report(
        session, target_date_str="2026-11-20", force=False, now_ts=now_ts
    )
    assert res1 is True
    assert len(sent_msgs) == 1
    report_text = sent_msgs[0]

    assert "Laporan 20 Nov 2026 (Warung Demo)" in report_text
    assert "3,500 kWh" in report_text
    assert "Biaya: ±Rp5.056" in report_text
    assert "1.100,0 W" in report_text

    # Cek scheduled_reports_log
    log_entry = session.scalar(
        select(ScheduledReportsLog).where(
            ScheduledReportsLog.report_type == "daily",
            ScheduledReportsLog.report_date == "2026-11-20",
        )
    )
    assert log_entry is not None
    assert log_entry.sent_at == now_ts

    # Kirim kedua kali tanpa force -> Harus dilewati (idempotent)
    res2 = generate_and_send_daily_report(
        session, target_date_str="2026-11-20", force=False, now_ts=now_ts
    )
    assert res2 is False
    assert len(sent_msgs) == 1  # Tidak bertambah!


def test_daily_report_disabled_when_report_enabled_false():
    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)

    # Matikan report_enabled
    setting_re = session.scalar(select(Setting).where(Setting.key == "report_enabled"))
    setting_re.value = "false"
    session.commit()

    res = generate_and_send_daily_report(session, target_date_str="2026-11-20")
    assert res is False
    assert len(sent_msgs) == 0


def test_weekly_report_generation_and_idempotency():
    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)

    sim_dt = datetime(2026, 11, 22, 20, 0, 0, tzinfo=TZ_WIB)  # Minggu
    now_ts = int(sim_dt.timestamp())

    session.add(
        Device(id="demo-1", name="Warung Demo", mcb_watt=2200, last_seen_at=now_ts, status="online")
    )
    # Tambahkan daily_stats untuk minggu ini
    session.add(
        DailyStat(
            device_id="demo-1",
            day="2026-11-18",
            kwh=10.0,
            cost_rp=14447,
            tariff_sen=144470,
            p_max=1200.0,
        )
    )
    session.commit()

    res1 = generate_and_send_weekly_report(
        session, target_date_str="2026-11-22", force=False, now_ts=now_ts
    )
    assert res1 is True
    assert len(sent_msgs) == 1
    assert "Laporan Mingguan" in sent_msgs[0]

    # Idempotensi
    res2 = generate_and_send_weekly_report(
        session, target_date_str="2026-11-22", force=False, now_ts=now_ts
    )
    assert res2 is False
    assert len(sent_msgs) == 1


def test_report_not_logged_if_notification_fails():
    _, session = get_test_session()
    # Simulasikan kegagalan kirim
    set_notification_sender(lambda m: False)

    session.add(Device(id="demo-1", name="Warung Demo", mcb_watt=2200, status="online"))
    session.commit()

    res = generate_and_send_daily_report(session, target_date_str="2026-11-20")
    assert res is False

    # scheduled_reports_log TIDAK boleh terisi
    log_entry = session.scalar(
        select(ScheduledReportsLog).where(
            ScheduledReportsLog.report_type == "daily",
            ScheduledReportsLog.report_date == "2026-11-20",
        )
    )
    assert log_entry is None


def test_telegram_failure_does_not_affect_ingest():
    _, session = get_test_session()
    set_notification_sender(lambda m: False)

    now_ts = 1736001000
    payload = {
        "ts": now_ts,
        "v": 220.0,
        "i": 1.0,
        "p": 220.0,
        "e": 10.0,
        "f": 50.0,
        "pf": 1.0,
    }
    # Ingest harus tetap sukses 100% dan tidak terganggu kegagalan telegram
    reading = process_telemetry_payload(session, "esp_test", payload)
    assert reading is not None
    assert reading.device_id == "esp_test"


def test_scheduler_inactive_in_app_env_test():
    s = Settings(app_env="test", scheduler_enabled=True, bot_enabled=True)
    assert s.is_scheduler_active is False
    assert s.is_bot_active is False


@pytest.mark.anyio
async def test_scheduler_reschedule_daily_report():
    # Inisialisasi job
    init_scheduler_jobs(report_hour=21)
    job = scheduler.get_job("daily_report_job")
    assert job is not None

    if not scheduler.running:
        scheduler.start(paused=True)

    reschedule_daily_report(22)
    job = scheduler.get_job("daily_report_job")
    hour_field = next(str(f) for f in job.trigger.fields if f.name == "hour")
    assert hour_field == "22"

    scheduler.shutdown(wait=False)
