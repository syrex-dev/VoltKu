import time

from app.models import Device, HourlyStat, Reading
from app.mqtt_ingest import IngestService, get_device_status, process_telemetry_payload
from app.services.delta import reset_rejection_tracker
from mysql_test_helper import open_clean_test_session
from sqlalchemy import select


def get_test_session():
    _, session = open_clean_test_session()
    return session


def test_ingest_auto_registers_unknown_device():
    session = get_test_session()
    reset_rejection_tracker()

    payload = {
        "ts": 1736000000,
        "v": 220.0,
        "i": 1.0,
        "p": 220.0,
        "e": 10.0,
        "f": 50.0,
        "pf": 0.98,
        "rssi": -60,
    }
    reading = process_telemetry_payload(session, "esp_new_device", payload, default_mcb_watt=1300)
    assert reading is not None
    assert reading.device_id == "esp_new_device"
    assert reading.delta_kwh == 0.0

    # Pastikan device otomatis dibuat di tabel devices
    device = session.scalar(select(Device).where(Device.id == "esp_new_device"))
    assert device is not None
    assert device.mcb_watt == 1300
    assert device.status == "online"
    assert device.last_data_ts == 1736000000
    assert device.last_seen_at is not None


def test_replay_old_data_does_not_rewind_timestamps():
    session = get_test_session()
    reset_rejection_tracker()

    p_latest = {
        "ts": 1736000050,
        "v": 220.0,
        "i": 1.0,
        "p": 220.0,
        "e": 10.005,
        "f": 50.0,
        "pf": 0.98,
        "rssi": -60,
    }
    process_telemetry_payload(session, "esp_replay_test", p_latest)
    dev = session.scalar(select(Device).where(Device.id == "esp_replay_test"))
    assert dev is not None
    assert dev.last_data_ts == 1736000050
    initial_last_seen = dev.last_seen_at
    assert initial_last_seen is not None

    # Replay data lampau (ts=1736000010 < 1736000050)
    p_old = {
        "ts": 1736000010,
        "v": 220.0,
        "i": 1.0,
        "p": 220.0,
        "e": 10.001,
        "f": 50.0,
        "pf": 0.98,
        "rssi": -60,
    }
    process_telemetry_payload(session, "esp_replay_test", p_old)
    session.refresh(dev)

    # Verifikasi: last_data_ts TETAP 1736000050 (tidak mundur!)
    assert dev.last_data_ts == 1736000050
    # Verifikasi: last_seen_at tidak mundur
    assert dev.last_seen_at >= initial_last_seen


def test_ingest_duplicate_ignored():
    session = get_test_session()
    reset_rejection_tracker()

    payload = {
        "ts": 1736000000,
        "v": 220.0,
        "i": 1.0,
        "p": 220.0,
        "e": 10.0,
        "f": 50.0,
        "pf": 0.98,
        "rssi": -60,
    }
    r1 = process_telemetry_payload(session, "esp_dup", payload)
    r2 = process_telemetry_payload(session, "esp_dup", payload)

    assert r1 is not None and r2 is not None
    assert r1.id == r2.id  # Objek yang sama dikembalikan tanpa membuat duplikat di DB

    stmt = select(Reading).where(Reading.device_id == "esp_dup")
    all_readings = list(session.scalars(stmt).all())
    assert len(all_readings) == 1


def test_ingest_out_of_order_reconciliation():
    session = get_test_session()
    reset_rejection_tracker()

    # Kirim ts1: e=10.000
    p1 = {"ts": 1736000000, "v": 220.0, "i": 1.0, "p": 220.0, "e": 10.0, "f": 50.0, "pf": 1.0}
    r1 = process_telemetry_payload(session, "esp_ooo", p1)
    assert r1 is not None and r1.delta_kwh == 0.0

    # Kirim ts3 lebih dulu (out of order): e=10.010 (+0.010 dari ts1)
    p3 = {"ts": 1736000020, "v": 220.0, "i": 1.0, "p": 220.0, "e": 10.010, "f": 50.0, "pf": 1.0}
    r3 = process_telemetry_payload(session, "esp_ooo", p3)
    assert r3 is not None and r3.delta_kwh == 0.010

    # Sekarang kirim ts2 (sampel yang terlambat di tengah ts1 dan ts3): e=10.004
    p2 = {"ts": 1736000010, "v": 220.0, "i": 1.0, "p": 220.0, "e": 10.004, "f": 50.0, "pf": 1.0}
    r2 = process_telemetry_payload(session, "esp_ooo", p2)
    assert r2 is not None
    # Delta ts2 terhadap ts1: 10.004 - 10.000 = 0.004
    assert r2.delta_kwh == 0.004

    # Periksa apakah delta ts3 telah direkonsiliasi otomatis terhadap ts2: 10.010 - 10.004 = 0.006!
    session.refresh(r3)
    assert r3.delta_kwh == 0.006

    # Cek total agregat kwh di hourly_stat: 0.0 + 0.004 + 0.006 = 0.010!
    h_stat = session.scalar(
        select(HourlyStat).where(
            HourlyStat.device_id == "esp_ooo",
            HourlyStat.hour_start == (1736000000 // 3600) * 3600,
        )
    )
    assert h_stat is not None
    assert h_stat.kwh == 0.010


def test_ingest_queue_worker():
    service = IngestService(max_queue_size=10)
    service.start_worker()

    try:
        # Enqueue pesan
        ok = service.enqueue_message("energy/esp_test/status", "online")
        assert ok is True
        time.sleep(0.5)
    finally:
        service.stop_worker()


def test_device_offline_detection():
    now = 1736000500
    # Device baru online (last_seen_at baru 10 detik lalu)
    dev_online = Device(id="d1", name="d1", last_seen_at=now - 10, status="online")
    assert get_device_status(dev_online, now_utc=now) == "online"

    # Device tidak kirim data > 120 detik (150 detik lalu) -> offline
    dev_timed_out = Device(id="d2", name="d2", last_seen_at=now - 150, status="online")
    assert get_device_status(dev_timed_out, now_utc=now) == "offline"

    # Device dengan status eksplisit 'offline' (LWT)
    dev_lwt = Device(id="d3", name="d3", last_seen_at=now - 10, status="offline")
    assert get_device_status(dev_lwt, now_utc=now) == "offline"


def test_ingest_non_standard_status_payload_behavior():
    """Perilaku ingest saat menerima payload status selain online/offline (misal: 'error_pzem').

    Backend mengabaikan status non-standar sehingga status perangkat tidak rusak,
    perangkat baru dengan status error tidak dibuat otomatis, dan status perangkat
    yang sudah online tetap online.
    """
    from app.db import SessionLocal

    service = IngestService()

    # 1. Status 'error_pzem' untuk device yang belum terdaftar: tidak membuat entri di DB
    service._handle_message("energy/dev_unknown/status", "error_pzem")
    with SessionLocal() as session:
        dev_unknown = session.scalar(select(Device).where(Device.id == "dev_unknown"))
        assert dev_unknown is None

    # 2. Status 'online' mendaftarkan device dengan status online
    service._handle_message("energy/dev_known/status", "online")
    with SessionLocal() as session:
        dev_known = session.scalar(select(Device).where(Device.id == "dev_known"))
        assert dev_known is not None
        assert dev_known.status == "online"
        last_seen = dev_known.last_seen_at

    # 3. Payload non-standar tidak mengubah status device yang sudah online
    for non_std_status in ("error_pzem", "rebooting", "unknown_code", "ERROR"):
        service._handle_message("energy/dev_known/status", non_std_status)
        with SessionLocal() as session:
            dev = session.scalar(select(Device).where(Device.id == "dev_known"))
            assert dev is not None
            assert dev.status == "online"
            # last_seen_at tidak berubah
            assert dev.last_seen_at == last_seen

