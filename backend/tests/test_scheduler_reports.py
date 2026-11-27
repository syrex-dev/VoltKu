from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from app.config import Settings
from app.models import (
    DailyStat,
    Device,
    Reading,
    ScheduledReportsLog,
    Setting,
    User,
    UserNotification,
    UserSetting,
)
from app.mqtt_ingest import process_telemetry_payload
from app.services.notifier import set_notification_sender
from app.services.report_generator import (
    check_and_send_catchup_reports,
    generate_and_send_daily_report,
    generate_and_send_weekly_report,
)
from app.services.scheduler import init_scheduler_jobs, reschedule_daily_report, scheduler
from mysql_test_helper import open_clean_test_session
from sqlalchemy import select

TZ_WIB = ZoneInfo("Asia/Jakarta")


def get_test_session():
    engine, session = open_clean_test_session()
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

    reschedule_daily_report(20, "Asia/Makassar")
    job_wita = scheduler.get_job("daily_report_job")
    hour_wita = next(str(f) for f in job_wita.trigger.fields if f.name == "hour")
    assert hour_wita == "20"
    assert str(job_wita.trigger.timezone) == "Asia/Makassar"

    weekly_wita = scheduler.get_job("weekly_report_job")
    assert weekly_wita is not None
    assert str(weekly_wita.trigger.timezone) == "Asia/Makassar"

    scheduler.shutdown(wait=False)


def test_daily_report_and_catchup_honor_wita_wit_timezone():
    """Saat zona waktu diset ke WITA/WIT, jadwal & label laporan memakai zona tersebut."""
    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)

    session.add(Setting(key="report_timezone", value="Asia/Makassar"))
    session.add(Device(id="dev-wita", name="Panel Makassar", mcb_watt=2200, status="online"))
    session.commit()

    # 21:10 WITA (= 20:10 WIB) sudah melewati jam 21:00 WITA
    dt_wita = datetime(2026, 11, 20, 21, 10, 0, tzinfo=ZoneInfo("Asia/Makassar"))
    actions = check_and_send_catchup_reports(session, now_dt=dt_wita)
    assert actions == ["catchup_daily_2026-11-20"]
    assert len(sent_msgs) == 1
    assert "WITA" in sent_msgs[0]


def test_catchup_reports_restart_2230_sends_once_and_no_duplicate():
    """Restart 22.30 WIB (> 21.00) -> terkirim sekali; restart kedua kali -> tidak duplikat."""
    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)

    session.add(Device(id="demo-1", name="Warung Demo", mcb_watt=2200, status="online"))
    session.commit()

    # Jam 22:30 WIB pada tanggal 2026-11-20
    dt_2230 = datetime(2026, 11, 20, 22, 30, 0, tzinfo=TZ_WIB)

    # Startup 1: Catch-up harus mendeteksi laporan belum dikirim hari ini
    actions1 = check_and_send_catchup_reports(session, now_dt=dt_2230)
    assert actions1 == ["catchup_daily_2026-11-20"]
    assert len(sent_msgs) == 1

    # Startup 2: Restart ulang di waktu yang sama -> tidak ada duplikasi
    actions2 = check_and_send_catchup_reports(session, now_dt=dt_2230)
    assert actions2 == []
    assert len(sent_msgs) == 1


def test_catchup_reports_restart_0030_next_day_does_not_send_yesterday():
    """Restart 00.30 hari berikutnya -> tidak mengirim laporan kemarin."""
    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)

    session.add(Device(id="demo-1", name="Warung Demo", mcb_watt=2200, status="online"))
    session.commit()

    # Jam 00:30 WIB pada hari berikutnya (2026-11-21)
    # Laporan kemarin (2026-11-20) terlewat dan TIDAK boleh dikirim ulang
    # Jam sekarang (00:30) belum mencapai report_hour (21:00) untuk hari baru
    dt_0030 = datetime(2026, 11, 21, 0, 30, 0, tzinfo=TZ_WIB)

    actions = check_and_send_catchup_reports(session, now_dt=dt_0030)
    assert actions == []
    assert len(sent_msgs) == 0

    # Pastikan tidak ada log yang dibuat untuk hari kemarin
    yesterday_log = session.scalar(
        select(ScheduledReportsLog).where(
            ScheduledReportsLog.report_date == "2026-11-20"
        )
    )
    assert yesterday_log is None


def test_catchup_weekly_report_on_sunday_past_2000():
    """Catch-up laporan mingguan pada hari Minggu jam >= 20.00 WIB."""
    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)

    session.add(Device(id="demo-1", name="Warung Demo", mcb_watt=2200, status="online"))
    session.commit()

    # Minggu, 2026-11-22 jam 21:15 WIB (weekday = 6, hour = 21 >= 20 dan >= report_hour 21)
    dt_sunday = datetime(2026, 11, 22, 21, 15, 0, tzinfo=TZ_WIB)

    actions = check_and_send_catchup_reports(session, now_dt=dt_sunday)
    assert "catchup_daily_2026-11-22" in actions
    assert "catchup_weekly_2026-11-22" in actions
    assert len(sent_msgs) == 2


def test_reports_skip_when_all_devices_are_sim():
    """Jika tidak ada perangkat riil (hanya sim-), laporan tidak mengirim pesan kosong."""
    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)

    # Hanya ada perangkat simulasi
    session.add(Device(id="sim-warung", name="Sim Warung", mcb_watt=2200, status="online"))
    session.commit()

    # Laporan harian
    res_daily = generate_and_send_daily_report(session, target_date_str="2026-11-20")
    assert res_daily is False
    assert len(sent_msgs) == 0

    # Laporan mingguan
    res_weekly = generate_and_send_weekly_report(session, target_date_str="2026-11-22")
    assert res_weekly is False
    assert len(sent_msgs) == 0


def test_multi_tenant_reports_independent_timezones_and_inbox():
    """Tenant di WIT dan WITA menerima laporan ke Inbox sesuai jam/zona waktu masing-masing."""
    _, session = get_test_session()
    set_notification_sender(None)  # Channel Telegram global tidak aktif

    u_wit = User(name="Budi WIT", email="wit@example.com", password_hash="x", is_active=1)
    u_wita = User(name="Sari WITA", email="wita@example.com", password_hash="x", is_active=1)
    session.add_all([u_wit, u_wita])
    session.flush()

    session.add_all(
        [
            UserSetting(user_id=u_wit.id, key="report_timezone", value="Asia/Jayapura"),
            UserSetting(user_id=u_wit.id, key="report_hour", value="20"),
            UserSetting(user_id=u_wita.id, key="report_timezone", value="Asia/Makassar"),
            UserSetting(user_id=u_wita.id, key="report_hour", value="21"),
            Device(
                id="dev-wit-1",
                name="Rumah Jayapura",
                mcb_watt=2200,
                owner_user_id=u_wit.id,
                status="online",
            ),
            Device(
                id="dev-wita-1",
                name="Rumah Makassar",
                mcb_watt=2200,
                owner_user_id=u_wita.id,
                status="online",
            ),
        ]
    )
    session.commit()

    # 20:10 WIT = 19:10 WITA -> hanya user WIT yang sudah waktunya
    dt_t1 = datetime(2026, 11, 20, 20, 10, 0, tzinfo=ZoneInfo("Asia/Jayapura"))
    actions1 = check_and_send_catchup_reports(session, now_dt=dt_t1)
    assert f"tenant_{u_wit.id}_daily_2026-11-20" in actions1
    assert f"tenant_{u_wita.id}_daily_2026-11-20" not in actions1

    wit_notifs = session.scalars(
        select(UserNotification).where(UserNotification.user_id == u_wit.id)
    ).all()
    wita_notifs = session.scalars(
        select(UserNotification).where(UserNotification.user_id == u_wita.id)
    ).all()
    assert len(wit_notifs) == 1
    assert "WIT" in wit_notifs[0].body
    assert len(wita_notifs) == 0

    # 21:05 WITA = 22:05 WIT -> sekarang user WITA mendapat laporan, user WIT tidak duplikat
    dt_t2 = datetime(2026, 11, 20, 21, 5, 0, tzinfo=ZoneInfo("Asia/Makassar"))
    actions2 = check_and_send_catchup_reports(session, now_dt=dt_t2)
    assert f"tenant_{u_wita.id}_daily_2026-11-20" in actions2
    assert f"tenant_{u_wit.id}_daily_2026-11-20" not in actions2

    wit_notifs_after = session.scalars(
        select(UserNotification).where(UserNotification.user_id == u_wit.id)
    ).all()
    wita_notifs_after = session.scalars(
        select(UserNotification).where(UserNotification.user_id == u_wita.id)
    ).all()
    assert len(wit_notifs_after) == 1
    assert len(wita_notifs_after) == 1
    assert "WITA" in wita_notifs_after[0].body
