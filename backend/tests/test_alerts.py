from app.models import AlertState, Anomaly, Base, Device, Reading, Setting
from app.services.alert import evaluate_all_alerts
from app.services.notifier import set_notification_sender
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def get_test_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    # Seed default settings
    session.add(Setting(key="power_limit_w", value="2200"))
    session.add(Setting(key="alert_cooldown_min", value="15"))
    session.commit()
    return engine, session


def test_alert_skips_sim_devices():
    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)

    now_ts = 1736001000
    # Device simulasi
    session.add(Device(id="sim-warung", name="Sim Warung", mcb_watt=2200, last_seen_at=now_ts))

    # Masukkan 3 reading daya tinggi
    for i in range(3):
        session.add(
            Reading(
                device_id="sim-warung",
                ts=now_ts - 10 * i,
                v=220.0,
                i=15.0,
                p=3300.0,  # Jauh di atas 2200 W
                e_kwh=10.0,
                delta_kwh=0.1,
                f=50.0,
                pf=1.0,
                rssi=-60,
            )
        )
    session.commit()

    # Evaluasi dengan startup_ts 200 detik lalu (lewat grace period)
    messages = evaluate_all_alerts(session, now_ts=now_ts, startup_ts=now_ts - 200)

    # Harus diabaikan karena prefix 'sim-'
    assert len(messages) == 0
    assert len(sent_msgs) == 0


def test_alert_suppressed_during_startup_grace_period():
    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)

    now_ts = 1736001000
    session.add(Device(id="demo-1", name="Demo 1", mcb_watt=2200, last_seen_at=now_ts))
    for i in range(3):
        session.add(
            Reading(
                device_id="demo-1",
                ts=now_ts - 10 * i,
                v=220.0,
                i=15.0,
                p=3000.0,
                e_kwh=10.0,
                delta_kwh=0.1,
                f=50.0,
                pf=1.0,
                rssi=-60,
            )
        )
    session.commit()

    # startup_ts baru 50 detik lalu (< 120s grace period)
    messages = evaluate_all_alerts(session, now_ts=now_ts, startup_ts=now_ts - 50)
    assert len(messages) == 0
    assert len(sent_msgs) == 0


def test_alert_power_limit_lifecycle_cooldown_and_recovery():
    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)

    now_ts = 1736001000
    startup_ts = now_ts - 300
    session.add(
        Device(id="demo-1", name="Demo 1", mcb_watt=2200, last_seen_at=now_ts, status="online")
    )

    # 1. Tiga sampel daya tinggi dalam jendela 60 detik (> 2200 W)
    for i in range(3):
        session.add(
            Reading(
                device_id="demo-1",
                ts=now_ts - 10 * i,
                v=220.0,
                i=12.0,
                p=2640.0,
                e_kwh=10.0,
                delta_kwh=0.1,
                f=50.0,
                pf=1.0,
                rssi=-60,
            )
        )
    session.commit()

    # Trigger alert pertama
    msgs = evaluate_all_alerts(session, now_ts=now_ts, startup_ts=startup_ts)
    assert len(msgs) == 1
    assert "Daya melebihi batas" in msgs[0]

    # Cek alert_state di DB
    state = session.scalar(
        select(AlertState).where(
            AlertState.device_id == "demo-1", AlertState.alert_type == "power_limit"
        )
    )
    assert state is not None
    assert state.state == "active"
    assert state.last_notified_at == now_ts

    # Cek tabel anomalies
    anomaly = session.scalar(
        select(Anomaly).where(Anomaly.device_id == "demo-1", Anomaly.type == "power_limit")
    )
    assert anomaly is not None

    # 2. Cek Cooldown: 5 menit kemudian (cooldown diset 15 menit) -> Jangan kirim notifikasi ulang
    now_ts_5m = now_ts + 300
    dev = session.scalar(select(Device).where(Device.id == "demo-1"))
    dev.last_seen_at = now_ts_5m
    for i in range(3):
        session.add(
            Reading(
                device_id="demo-1",
                ts=now_ts_5m - 10 * i,
                v=220.0,
                i=12.0,
                p=2640.0,
                e_kwh=10.5,
                delta_kwh=0.1,
                f=50.0,
                pf=1.0,
                rssi=-60,
            )
        )
    session.commit()

    msgs_cooldown = evaluate_all_alerts(session, now_ts=now_ts_5m, startup_ts=startup_ts)
    assert len(msgs_cooldown) == 0  # Tertahan cooldown!

    # 3. Cek Pengingat: 16 menit kemudian (> 15 menit cooldown) -> Kirim pengingat berkala
    now_ts_16m = now_ts + 960
    dev.last_seen_at = now_ts_16m
    for i in range(3):
        session.add(
            Reading(
                device_id="demo-1",
                ts=now_ts_16m - 10 * i,
                v=220.0,
                i=12.0,
                p=2640.0,
                e_kwh=11.0,
                delta_kwh=0.1,
                f=50.0,
                pf=1.0,
                rssi=-60,
            )
        )
    session.commit()

    msgs_reminder = evaluate_all_alerts(session, now_ts=now_ts_16m, startup_ts=startup_ts)
    assert len(msgs_reminder) == 1
    assert "PENGINGAT" in msgs_reminder[0]

    # 4. Histeresis & Pemulihan: Daya turun di bawah 0.95 * 2200 W = 2090 W (misal 1500 W)
    now_ts_recover = now_ts_16m + 70
    dev.last_seen_at = now_ts_recover
    for i in range(3):
        session.add(
            Reading(
                device_id="demo-1",
                ts=now_ts_recover - 10 * i,
                v=220.0,
                i=7.0,
                p=1500.0,
                e_kwh=11.2,
                delta_kwh=0.1,
                f=50.0,
                pf=1.0,
                rssi=-60,
            )
        )
    session.commit()

    msgs_recover = evaluate_all_alerts(session, now_ts=now_ts_recover, startup_ts=startup_ts)
    assert len(msgs_recover) == 1
    assert "PULIH" in msgs_recover[0]

    session.refresh(state)
    assert state.state == "cleared"


def test_alert_voltage_low_high_and_recovery():
    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)

    now_ts = 1736001000
    startup_ts = now_ts - 300
    session.add(
        Device(id="demo-1", name="Demo 1", mcb_watt=2200, last_seen_at=now_ts, status="online")
    )

    # Tegangan rendah (< 200 V) dalam jendela 30 detik
    for i in range(2):
        session.add(
            Reading(
                device_id="demo-1",
                ts=now_ts - 10 * i,
                v=192.0,
                i=2.0,
                p=380.0,
                e_kwh=5.0,
                delta_kwh=0.05,
                f=50.0,
                pf=0.98,
                rssi=-60,
            )
        )
    session.commit()

    msgs = evaluate_all_alerts(session, now_ts=now_ts, startup_ts=startup_ts)
    assert any("Tegangan rendah" in m for m in msgs)

    # Pulih ke rentang 205 - 235 V (setelah jendela lama 30 detik berlalu)
    now_ts_recover = now_ts + 45
    dev = session.scalar(select(Device).where(Device.id == "demo-1"))
    dev.last_seen_at = now_ts_recover
    for i in range(2):
        session.add(
            Reading(
                device_id="demo-1",
                ts=now_ts_recover - 10 * i,
                v=220.0,
                i=2.0,
                p=440.0,
                e_kwh=5.1,
                delta_kwh=0.05,
                f=50.0,
                pf=0.98,
                rssi=-60,
            )
        )
    session.commit()

    msgs_rec = evaluate_all_alerts(session, now_ts=now_ts_recover, startup_ts=startup_ts)
    assert any("Tegangan normal kembali" in m for m in msgs_rec)


def test_alert_offline_and_recovery():
    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)

    now_ts = 1736001000
    startup_ts = now_ts - 300
    # Device offline (last seen 150 detik lalu > 120s)
    session.add(
        Device(
            id="demo-1",
            name="Demo 1",
            mcb_watt=2200,
            last_seen_at=now_ts - 150,
            status="online",
        )
    )
    session.commit()

    msgs = evaluate_all_alerts(session, now_ts=now_ts, startup_ts=startup_ts)
    assert any("Perangkat offline" in m for m in msgs)

    # Device online kembali (last seen = now)
    now_ts_online = now_ts + 60
    dev = session.scalar(select(Device).where(Device.id == "demo-1"))
    dev.last_seen_at = now_ts_online
    dev.status = "online"
    session.commit()

    msgs_online = evaluate_all_alerts(session, now_ts=now_ts_online, startup_ts=startup_ts)
    assert any("Perangkat online kembali" in m for m in msgs_online)


def test_alert_state_only_updates_on_successful_dispatch():
    _, session = get_test_session()
    # Simulasikan kegagalan jaringan / pengiriman
    set_notification_sender(lambda m: False)

    now_ts = 1736001000
    startup_ts = now_ts - 300
    session.add(
        Device(
            id="demo-1",
            name="Demo 1",
            mcb_watt=2200,
            last_seen_at=now_ts - 150,
            status="online",
        )
    )
    session.commit()

    # Ketika pengiriman gagal: alert_state TIDAK boleh diperbarui ke active
    evaluate_all_alerts(session, now_ts=now_ts, startup_ts=startup_ts)
    state = session.scalar(
        select(AlertState).where(
            AlertState.device_id == "demo-1", AlertState.alert_type == "offline"
        )
    )
    assert state is None
