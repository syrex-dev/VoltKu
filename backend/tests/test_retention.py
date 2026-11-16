from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.models import Base, DailyStat, Device, HourlyStat, Reading
from app.mqtt_ingest import validate_telemetry_payload
from app.services.retention import clean_old_readings, get_retention_cutoff_ts
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

TZ_WIB = ZoneInfo("Asia/Jakarta")


def get_test_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    return engine, session_factory()


def test_retention_cutoff_boundary_wib():
    # Simulasi jam 15.00 WIB tanggal 2026-11-20
    sim_dt = datetime(2026, 11, 20, 15, 0, 0, tzinfo=TZ_WIB)
    now_ts = int(sim_dt.timestamp())

    cutoff_ts = get_retention_cutoff_ts(now_ts)
    cutoff_dt = datetime.fromtimestamp(cutoff_ts, tz=TZ_WIB)

    # 14 hari penuh lampau dari 20 Nov = 6 Nov pukul 00:00:00 WIB
    assert cutoff_dt.year == 2026
    assert cutoff_dt.month == 11
    assert cutoff_dt.day == 6
    assert cutoff_dt.hour == 0
    assert cutoff_dt.minute == 0
    assert cutoff_dt.second == 0


def test_retention_incoming_data_rejected_if_older_than_cutoff():
    sim_dt = datetime(2026, 11, 20, 12, 0, 0, tzinfo=TZ_WIB)
    now_ts = int(sim_dt.timestamp())
    cutoff_ts = get_retention_cutoff_ts(now_ts)

    # 1 detik sebelum cutoff -> ditolak
    payload_old = {
        "ts": cutoff_ts - 1,
        "v": 220.0,
        "i": 1.0,
        "p": 220.0,
        "e": 10.0,
        "f": 50.0,
        "pf": 1.0,
    }
    is_valid, err = validate_telemetry_payload(payload_old, check_retention=True, now_utc=now_ts)
    assert is_valid is False
    assert "retention cutoff" in str(err)

    # Tepat di cutoff -> diterima
    payload_valid = dict(payload_old, ts=cutoff_ts)
    is_valid2, err2 = validate_telemetry_payload(
        payload_valid, check_retention=True, now_utc=now_ts
    )
    assert is_valid2 is True
    assert err2 is None


def test_retention_clean_preserves_last_sample_per_device_and_stats():
    _, session = get_test_session()

    # Setup device
    session.add(Device(id="dev-active", name="Active Device", mcb_watt=2200))
    session.add(Device(id="dev-dormant", name="Dormant Device", mcb_watt=2200))

    sim_dt = datetime(2026, 11, 20, 12, 0, 0, tzinfo=TZ_WIB)
    cutoff_ts = get_retention_cutoff_ts(int(sim_dt.timestamp()))

    # dev-active punya:
    # 3 reading sebelum cutoff (lama)
    # 2 reading setelah cutoff (baru)
    for i in range(1, 4):
        session.add(
            Reading(
                device_id="dev-active",
                ts=cutoff_ts - (i * 3600),
                v=220.0,
                i=1.0,
                p=220.0,
                e_kwh=10.0 + i,
                delta_kwh=0.1,
                f=50.0,
                pf=1.0,
                rssi=-60,
            )
        )
    for i in range(1, 3):
        session.add(
            Reading(
                device_id="dev-active",
                ts=cutoff_ts + (i * 3600),
                v=220.0,
                i=1.0,
                p=220.0,
                e_kwh=20.0 + i,
                delta_kwh=0.1,
                f=50.0,
                pf=1.0,
                rssi=-60,
            )
        )

    # dev-dormant HANYA punya reading sebelum cutoff (lama)!
    # Sampel terakhirnya (ts = cutoff_ts - 1000) TIDAK BOLEH dihapus!
    session.add(
        Reading(
            device_id="dev-dormant",
            ts=cutoff_ts - 5000,
            v=220.0,
            i=1.0,
            p=220.0,
            e_kwh=5.0,
            delta_kwh=0.1,
            f=50.0,
            pf=1.0,
            rssi=-60,
        )
    )
    session.add(
        Reading(
            device_id="dev-dormant",
            ts=cutoff_ts - 1000,
            v=220.0,
            i=1.0,
            p=220.0,
            e_kwh=5.1,
            delta_kwh=0.1,
            f=50.0,
            pf=1.0,
            rssi=-60,
        )
    )

    # Tambahkan hourly_stats & daily_stats pada rentang lama (sebelum cutoff)
    old_day_str = (datetime.fromtimestamp(cutoff_ts, tz=TZ_WIB) - timedelta(days=2)).strftime(
        "%Y-%m-%d"
    )
    session.add(
        DailyStat(
            device_id="dev-active",
            day=old_day_str,
            kwh=8.5,
            cost_rp=12280,
            tariff_sen=144470,
            p_max=1200.0,
        )
    )
    session.add(
        HourlyStat(
            device_id="dev-active",
            hour_start=cutoff_ts - 86400,
            kwh=0.5,
            p_avg=500.0,
            p_max=700.0,
            p_min=300.0,
            samples=360,
        )
    )
    session.commit()

    # Jalankan pembersihan retensi dengan batch kecil (batch_size=2)
    deleted = clean_old_readings(session, cutoff_ts, batch_size=2)

    # dev-active: 3 reading lama terhapus
    # dev-dormant: 1 reading lama terhapus, 1 reading terakhir DIPERTAHANKAN
    # Total terhapus = 3 + 1 = 4
    assert deleted == 4

    # Verifikasi sisa readings dev-active
    active_readings = session.scalars(
        select(Reading).where(Reading.device_id == "dev-active")
    ).all()
    assert len(active_readings) == 2
    assert all(r.ts >= cutoff_ts for r in active_readings)

    # Verifikasi dev-dormant masih memiliki sampel terakhirnya!
    dormant_readings = session.scalars(
        select(Reading).where(Reading.device_id == "dev-dormant")
    ).all()
    assert len(dormant_readings) == 1
    assert dormant_readings[0].ts == (cutoff_ts - 1000)

    # Verifikasi daily_stats dan hourly_stats TIDAK terhapus / tidak rusak
    daily = session.scalar(
        select(DailyStat).where(DailyStat.device_id == "dev-active", DailyStat.day == old_day_str)
    )
    assert daily is not None
    assert daily.kwh == 8.5
    assert daily.cost_rp == 12280

    hourly = session.scalar(
        select(HourlyStat).where(
            HourlyStat.device_id == "dev-active", HourlyStat.hour_start == cutoff_ts - 86400
        )
    )
    assert hourly is not None
    assert hourly.kwh == 0.5


def test_process_telemetry_payload_rejects_older_than_cutoff():
    """Ingest pipeline menolak data yang lebih tua dari cutoff retensi."""
    from app.mqtt_ingest import process_telemetry_payload

    _, session = get_test_session()
    now_ts = int(datetime(2026, 11, 20, 12, 0, 0, tzinfo=TZ_WIB).timestamp())
    cutoff_ts = get_retention_cutoff_ts(now_ts)

    session.add(Device(id="demo-1", name="Demo 1", mcb_watt=2200))
    session.commit()

    payload_old = {
        "ts": cutoff_ts - 100,  # Lebih tua dari cutoff 14 hari
        "v": 220.0,
        "i": 1.0,
        "p": 220.0,
        "e": 10.0,
        "f": 50.0,
        "pf": 1.0,
    }

    # Ingest dengan check_retention=True harus mengembalikan None
    res = process_telemetry_payload(
        session, "demo-1", payload_old, check_retention=True, now_utc=now_ts
    )
    assert res is None, "Data lebih tua dari cutoff retensi harus ditolak"

    # Verifikasi tidak ada reading tersimpan
    readings = session.scalars(select(Reading).where(Reading.device_id == "demo-1")).all()
    assert len(readings) == 0
