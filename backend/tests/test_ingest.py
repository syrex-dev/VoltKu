import time

from app.models import Base, Device, HourlyStat, Reading
from app.mqtt_ingest import IngestService, process_telemetry_payload
from app.services.delta import reset_rejection_tracker
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def get_test_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    return session_factory()


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
