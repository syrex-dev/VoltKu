import json

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

    # Masukkan 7 reading daya tinggi (memenuhi jendela 60 detik)
    for i in range(7):
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

    # 1. Tujuh sampel daya tinggi dalam jendela 60 detik (> 2200 W)
    for i in range(7):
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
    for i in range(7):
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
    for i in range(7):
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
    for i in range(7):
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


def test_alert_state_persists_across_restart_and_no_duplicate_notification():
    """State alert tahan restart (instance evaluator baru, tidak ada notifikasi dobel)."""
    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)

    now_ts = 1736001000
    startup_ts = now_ts - 300
    session.add(
        Device(id="demo-1", name="Demo 1", mcb_watt=2200, last_seen_at=now_ts, status="online")
    )

    # 1. Masukkan sampel overload dan picu alert pertama
    for i in range(7):
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

    msgs_1 = evaluate_all_alerts(session, now_ts=now_ts, startup_ts=startup_ts)
    assert len(msgs_1) == 1
    assert "Daya melebihi batas" in msgs_1[0]
    assert len(sent_msgs) == 1

    # 2. Simulasi RESTART BACKEND:
    # Instance evaluator baru (startup_ts baru, misal 130 detik setelah startup baru)
    restart_ts = now_ts + 20
    new_startup_ts = restart_ts
    # > 120s (lewat grace period), tapi < 15 menit cooldown
    eval_ts_after_restart = restart_ts + 130

    # Tambah sampel pembacaan saat restart berjalan
    dev = session.scalar(select(Device).where(Device.id == "demo-1"))
    dev.last_seen_at = eval_ts_after_restart
    for i in range(7):
        session.add(
            Reading(
                device_id="demo-1",
                ts=eval_ts_after_restart - 10 * i,
                v=220.0,
                i=12.0,
                p=2640.0,
                e_kwh=10.2,
                delta_kwh=0.1,
                f=50.0,
                pf=1.0,
                rssi=-60,
            )
        )
    session.commit()

    # Evaluasi dengan instance evaluator baru
    msgs_2 = evaluate_all_alerts(session, now_ts=eval_ts_after_restart, startup_ts=new_startup_ts)
    # TIDAK BOLEH ada notifikasi dobel (karena alert_state di DB masih aktif dan dalam cooldown)
    assert len(msgs_2) == 0, "Evaluator baru pasca-restart tidak boleh mengirim notifikasi dobel"
    assert len(sent_msgs) == 1, "Total notifikasi terkirim harus tetap 1"

    # 3. Sekarang kirim daya normal (pemulihan)
    eval_ts_recovery = eval_ts_after_restart + 70
    dev.last_seen_at = eval_ts_recovery
    for i in range(7):
        session.add(
            Reading(
                device_id="demo-1",
                ts=eval_ts_recovery - 10 * i,
                v=220.0,
                i=2.0,
                p=440.0,
                e_kwh=10.3,
                delta_kwh=0.01,
                f=50.0,
                pf=1.0,
                rssi=-60,
            )
        )
    session.commit()
    msgs_3 = evaluate_all_alerts(session, now_ts=eval_ts_recovery, startup_ts=new_startup_ts)
    assert len(msgs_3) == 1
    assert "PULIH" in msgs_3[0]

    # Verifikasi tabel anomalies: hanya ada 1 baris episode power_limit,
    # dan resolved_at tercatat di details_json setelah pemulihan
    anomalies = session.scalars(
        select(Anomaly).where(Anomaly.device_id == "demo-1")
    ).all()
    assert len(anomalies) == 1
    assert anomalies[0].type == "power_limit"
    anom_details = json.loads(anomalies[0].details_json)
    assert "resolved_at" in anom_details
    assert anom_details["resolved_at"] == eval_ts_recovery


def test_alert_power_window_coverage_gap_rejection():
    """Tiga sampel setelah restart/gap (cakupan hanya 20 detik) TIDAK boleh memicu alert daya."""
    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)

    now_ts = 1736001000
    startup_ts = now_ts - 300
    session.add(
        Device(id="demo-1", name="Demo 1", mcb_watt=2200, last_seen_at=now_ts, status="online")
    )

    # 3 sampel berjarak 10s: now, now-10, now-20 (cakupan 20s, jendela butuh 60s)
    for i in range(3):
        session.add(
            Reading(
                device_id="demo-1",
                ts=now_ts - 10 * i,
                v=220.0,
                i=15.0,
                p=3300.0,
                e_kwh=10.0,
                delta_kwh=0.1,
                f=50.0,
                pf=1.0,
                rssi=-60,
            )
        )
    session.commit()

    msgs = evaluate_all_alerts(session, now_ts=now_ts, startup_ts=startup_ts)
    assert len(msgs) == 0
    assert len(sent_msgs) == 0


def test_alert_power_window_coverage_exact_boundary():
    """Uji kasus tepat di batas jendela 60s untuk alert daya."""
    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)

    now_ts = 1736001000
    startup_ts = now_ts - 300
    session.add(
        Device(id="demo-1", name="Demo 1", mcb_watt=2200, last_seen_at=now_ts, status="online")
    )

    # Kasus A: Sampel tertua tepat di batas (now_ts - 45s <= window_start + 15s)
    # readings di now, now-10, now-20, now-30, now-45 -> lolos coverage!
    for offset in [0, 10, 20, 30, 45]:
        session.add(
            Reading(
                device_id="demo-1",
                ts=now_ts - offset,
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

    msgs_a = evaluate_all_alerts(session, now_ts=now_ts, startup_ts=startup_ts)
    assert len(msgs_a) == 1
    assert "Daya melebihi batas" in msgs_a[0]

    # Bersihkan state untuk kasus B
    session.query(AlertState).delete()
    session.query(Anomaly).delete()
    session.query(Reading).delete()
    session.commit()

    # Kasus B: Sampel tertua di now_ts - 44s (> now_ts - 45s) tanpa sampel awal -> Ditolak!
    for offset in [0, 10, 20, 30, 44]:
        session.add(
            Reading(
                device_id="demo-1",
                ts=now_ts - offset,
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

    msgs_b = evaluate_all_alerts(session, now_ts=now_ts, startup_ts=startup_ts)
    assert len(msgs_b) == 0  # Belum cukup mencakup 60s!

    # Kasus C: Sampel di now_ts - 44s TETAPI ada sampel sebelum jendela di now_ts - 65s
    # (dalam toleransi <= 15s dari window_start) yang juga overload -> Diterima!
    session.add(
        Reading(
            device_id="demo-1",
            ts=now_ts - 65,
            v=220.0,
            i=12.0,
            p=2640.0,
            e_kwh=9.9,
            delta_kwh=0.1,
            f=50.0,
            pf=1.0,
            rssi=-60,
        )
    )
    session.commit()

    msgs_c = evaluate_all_alerts(session, now_ts=now_ts, startup_ts=startup_ts)
    assert len(msgs_c) == 1
    assert "Daya melebihi batas" in msgs_c[0]


def test_alert_voltage_low_high_and_recovery():
    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)

    now_ts = 1736001000
    startup_ts = now_ts - 300
    session.add(
        Device(id="demo-1", name="Demo 1", mcb_watt=2200, last_seen_at=now_ts, status="online")
    )

    # Empat sampel tegangan rendah (< 200 V) dalam jendela 30 detik (now, now-10, now-20, now-30)
    for i in range(4):
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
    for i in range(4):
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

    # Verifikasi tabel anomalies: hanya ada 1 baris episode voltage,
    # dan resolved_at tercatat di details_json
    anomalies = session.scalars(
        select(Anomaly).where(Anomaly.device_id == "demo-1")
    ).all()
    assert len(anomalies) == 1
    assert anomalies[0].type == "voltage"
    anom_details = json.loads(anomalies[0].details_json)
    assert "resolved_at" in anom_details


def test_alert_voltage_window_coverage_gap_rejection():
    """Dua sampel setelah gap (cakupan 10 detik) TIDAK boleh memicu alert tegangan (jendela 30s)."""
    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)

    now_ts = 1736001000
    startup_ts = now_ts - 300
    session.add(
        Device(id="demo-1", name="Demo 1", mcb_watt=2200, last_seen_at=now_ts, status="online")
    )

    for i in range(2):
        session.add(
            Reading(
                device_id="demo-1",
                ts=now_ts - 10 * i,
                v=190.0,
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
    assert len(msgs) == 0


def test_alert_voltage_window_coverage_exact_boundary():
    """Uji kasus tepat di batas jendela 30s untuk alert tegangan."""
    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)

    now_ts = 1736001000
    startup_ts = now_ts - 300
    session.add(
        Device(id="demo-1", name="Demo 1", mcb_watt=2200, last_seen_at=now_ts, status="online")
    )

    # Batas 30s: window_start = now - 30. window_start + 15 = now - 15.
    # Kasus A: Tertua di now_ts - 15s -> Lolos coverage!
    for offset in [0, 10, 15]:
        session.add(
            Reading(
                device_id="demo-1",
                ts=now_ts - offset,
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

    msgs_a = evaluate_all_alerts(session, now_ts=now_ts, startup_ts=startup_ts)
    assert any("Tegangan rendah" in m for m in msgs_a)

    # Bersihkan state untuk kasus B
    session.query(AlertState).delete()
    session.query(Anomaly).delete()
    session.query(Reading).delete()
    session.commit()

    # Kasus B: Tertua di now_ts - 14s (> now_ts - 15s) tanpa sampel sebelum jendela -> Ditolak!
    for offset in [0, 10, 14]:
        session.add(
            Reading(
                device_id="demo-1",
                ts=now_ts - offset,
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

    msgs_b = evaluate_all_alerts(session, now_ts=now_ts, startup_ts=startup_ts)
    assert len(msgs_b) == 0

    # Kasus C: Tertua di now_ts - 14s TETAPI ada sampel sebelum jendela di now_ts - 35s
    # (<= 15s sebelum now_ts - 30) yang juga < 200 V -> Diterima!
    session.add(
        Reading(
            device_id="demo-1",
            ts=now_ts - 35,
            v=190.0,
            i=2.0,
            p=380.0,
            e_kwh=4.9,
            delta_kwh=0.05,
            f=50.0,
            pf=0.98,
            rssi=-60,
        )
    )
    session.commit()

    msgs_c = evaluate_all_alerts(session, now_ts=now_ts, startup_ts=startup_ts)
    assert any("Tegangan rendah" in m for m in msgs_c)


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

    # Verifikasi tabel anomalies: hanya ada 1 baris episode offline,
    # dan resolved_at tercatat di details_json
    anomalies = session.scalars(
        select(Anomaly).where(Anomaly.device_id == "demo-1")
    ).all()
    assert len(anomalies) == 1
    assert anomalies[0].type == "offline"
    anom_details = json.loads(anomalies[0].details_json)
    assert "resolved_at" in anom_details
    assert anom_details["resolved_at"] == now_ts_online


def test_null_notifier_returns_false():
    """NullNotifier mengembalikan False dan tidak melaporkan terkirim jika belum ada bot."""
    from app.services.notifier import send_alert_notification

    # Reset ke sender None (NullNotifier)
    set_notification_sender(None)
    res = send_alert_notification("Pesan uji coba tanpa bot")
    assert res is False


def test_alert_state_retry_on_next_tick_until_success():
    """Notifier gagal -> state tidak maju dan diulang di tick berikutnya; sukses -> tepat sekali."""
    _, session = get_test_session()

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

    # Tick 1: Notifier gagal (misal NullNotifier / bot belum aktif)
    set_notification_sender(lambda m: False)
    msgs_1 = evaluate_all_alerts(session, now_ts=now_ts, startup_ts=startup_ts)
    assert len(msgs_1) == 0

    state_1 = session.scalar(
        select(AlertState).where(
            AlertState.device_id == "demo-1", AlertState.alert_type == "offline"
        )
    )
    assert state_1 is None  # Tidak ditulis ke DB

    # Tick 2: Notifier berhasil terhubung (misal Telegram bot aktif)
    sent_msgs = []
    set_notification_sender(lambda m: sent_msgs.append(m) or True)
    now_ts_2 = now_ts + 10
    msgs_2 = evaluate_all_alerts(session, now_ts=now_ts_2, startup_ts=startup_ts)
    assert len(msgs_2) == 1
    assert len(sent_msgs) == 1
    assert "Perangkat offline" in msgs_2[0]

    state_2 = session.scalar(
        select(AlertState).where(
            AlertState.device_id == "demo-1", AlertState.alert_type == "offline"
        )
    )
    assert state_2 is not None
    assert state_2.state == "active"
    assert state_2.last_notified_at == now_ts_2

    # Tick 3: Masih offline, tapi dalam batas cooldown -> tidak dikirim ulang (tepat sekali)
    now_ts_3 = now_ts_2 + 10
    msgs_3 = evaluate_all_alerts(session, now_ts=now_ts_3, startup_ts=startup_ts)
    assert len(msgs_3) == 0
    assert len(sent_msgs) == 1  # Tetap 1, tidak duplikat


def test_offline_alert_only_after_120s_gap_not_immediate_lwt():
    """Alert notifikasi offline HANYA terpicu jika now - last_seen_at > 120s.

    Status tampilan (dashboard/get_device_status) langsung 'offline' jika LWT diterima,
    tetapi alert notifikasi TIDAK boleh langsung memicu alert sampai jeda telemetri > 120s.
    """
    from app.mqtt_ingest import get_device_status

    _, session = get_test_session()
    sent_msgs = []
    set_notification_sender(lambda m, **kw: sent_msgs.append(m) or True)

    now_ts = 1736001000
    startup_ts = now_ts - 500

    # Device menerima pesan LWT sehingga status='offline', tapi telemetri terakhir baru 30s lalu
    dev = Device(
        id="demo-lwt",
        name="Demo LWT",
        mcb_watt=2200,
        last_seen_at=now_ts - 30,
        status="offline",
    )
    session.add(dev)
    session.commit()

    # 1. Status tampilan untuk UI/API langsung offline karena LWT
    disp_status = get_device_status(dev, now_utc=now_ts)
    assert disp_status == "offline"

    # 2. Evaluator alert: jeda 30s <= 120s -> TIDAK memicu alert notifikasi
    msgs_1 = evaluate_all_alerts(session, now_ts=now_ts, startup_ts=startup_ts)
    assert len(msgs_1) == 0
    assert len(sent_msgs) == 0

    # 3. Batas 119s: belum lewat ambang 120s -> TIDAK memicu alert
    now_119 = dev.last_seen_at + 119
    msgs_119 = evaluate_all_alerts(session, now_ts=now_119, startup_ts=startup_ts)
    assert len(msgs_119) == 0
    assert len(sent_msgs) == 0

    # 4. Batas 121s: lewat ambang 120s -> MEMICU alert notifikasi tepat sekali
    now_121 = dev.last_seen_at + 121
    msgs_121 = evaluate_all_alerts(session, now_ts=now_121, startup_ts=startup_ts)
    assert len(msgs_121) == 1
    assert len(sent_msgs) == 1
    assert "Perangkat offline" in msgs_121[0]


def test_no_channel_mode_100_ticks_records_exactly_one_anomaly_and_zero_sends():
    """Mode tanpa kanal: anomali dicatat normal (notified=0), state aktif,

    100 tick evaluator -> tepat 1 episode anomali, 0 percobaan kirim.
    """
    from app.services.notifier import null_notifier

    _, session = get_test_session()
    # Atur ke mode tanpa kanal (null_notifier)
    set_notification_sender(null_notifier)

    start_ts = 1736001000
    startup_ts = start_ts - 500

    dev = Device(
        id="demo-nochannel",
        name="Demo No Channel",
        mcb_watt=2200,
        last_seen_at=start_ts - 200,  # Offline > 120s
        status="online",
    )
    session.add(dev)
    session.commit()

    # Jalankan 100 tick evaluator berturut-turut (interval 15 detik)
    for tick in range(100):
        tick_ts = start_ts + (tick * 15)
        sent = evaluate_all_alerts(session, now_ts=tick_ts, startup_ts=startup_ts)
        assert len(sent) == 0  # 0 pesan terkirim

    # Verifikasi database:
    # 1. Tepat 1 episode anomali tercatat
    anomalies = session.scalars(
        select(Anomaly).where(Anomaly.device_id == "demo-nochannel")
    ).all()
    assert len(anomalies) == 1
    anom = anomalies[0]
    assert anom.type == "offline"
    assert anom.notified == 0  # Ditandai notified=0 karena tidak ada kanal

    # 2. AlertState aktif dan tidak bolak-balik reset
    st = session.scalar(
        select(AlertState).where(
            AlertState.device_id == "demo-nochannel",
            AlertState.alert_type == "offline",
        )
    )
    assert st is not None
    assert st.state == "active"


def test_no_channel_mode_catchup_reports_does_not_assemble_reports():
    """Mode tanpa kanal: catch-up laporan tidak menyusun laporan."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from app.models import ScheduledReportsLog
    from app.services.notifier import null_notifier
    from app.services.report_generator import (
        check_and_send_catchup_reports,
        generate_and_send_daily_report,
    )

    _, session = get_test_session()
    set_notification_sender(null_notifier)

    # Tambah perangkat aktif
    session.add(Device(id="demo-dev", name="Demo Dev", mcb_watt=2200, last_seen_at=1736001000))
    session.commit()

    tz_wib = ZoneInfo("Asia/Jakarta")
    dt_catchup = datetime(2026, 1, 15, 22, 0, tzinfo=tz_wib)  # Jam 22.00 WIB (> 21.00)

    # Jalankan catch-up
    actions = check_and_send_catchup_reports(session, now_dt=dt_catchup)
    assert actions == []  # Tidak menyusun laporan apapun

    # Panggilan langsung generate_and_send_daily_report juga menolak saat tanpa kanal
    ok = generate_and_send_daily_report(session, target_date_str="2026-01-15")
    assert ok is False

    # Scheduled reports log tetap kosong
    logs = session.scalars(select(ScheduledReportsLog)).all()
    assert len(logs) == 0


def test_configured_channel_failure_does_not_advance_state():
    """Kanal terkonfigurasi tetapi gagal (misal network error):

    state TIDAK maju dan anomali tidak dicatat notified.
    """
    _, session = get_test_session()
    # Mock kanal yang terkonfigurasi tapi selalu gagal (mengembalikan False)
    set_notification_sender(lambda m, **kw: False)

    now_ts = 1736001000
    startup_ts = now_ts - 500

    dev = Device(
        id="demo-fail-chan",
        name="Demo Fail Channel",
        mcb_watt=2200,
        last_seen_at=now_ts - 200,
        status="online",
    )
    session.add(dev)
    session.commit()

    sent = evaluate_all_alerts(session, now_ts=now_ts, startup_ts=startup_ts)
    assert len(sent) == 0

    # Karena kanal gagal, state TIDAK maju
    st = session.scalar(
        select(AlertState).where(
            AlertState.device_id == "demo-fail-chan",
            AlertState.alert_type == "offline",
        )
    )
    assert st is None or st.state != "active"

    # Tidak ada anomali yang tersimpan
    anomalies = session.scalars(
        select(Anomaly).where(Anomaly.device_id == "demo-fail-chan")
    ).all()
    assert len(anomalies) == 0

