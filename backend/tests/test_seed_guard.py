import pytest
from app.models import Device
from mysql_test_helper import get_clean_mysql_engine
from sqlalchemy.orm import Session

from scripts.clean_device import check_clean_safety, clean_device
from scripts.seed_db import check_seed_safety


def test_seed_guard_allows_empty_database():
    test_engine = get_clean_mysql_engine()

    # Database kosong harus boleh tanpa flag
    check_seed_safety(test_engine, confirm_reset=False)


def test_seed_guard_allows_only_sim_devices():
    test_engine = get_clean_mysql_engine()

    with Session(bind=test_engine) as session:
        session.add(Device(id="sim-warung", name="Warung", mcb_watt=2200))
        session.add(Device(id="sim-bench", name="Bench", mcb_watt=2200))
        session.commit()

    # Hanya perangkat sim- harus boleh tanpa flag
    check_seed_safety(test_engine, confirm_reset=False)


def test_seed_guard_rejects_non_sim_devices_without_flag():
    test_engine = get_clean_mysql_engine()

    with Session(bind=test_engine) as session:
        session.add(Device(id="sim-warung", name="Warung", mcb_watt=2200))
        session.add(Device(id="esp32_device_1", name="ESP Real", mcb_watt=2200))
        session.commit()

    # Ada perangkat non-sim tanpa flag confirm_reset harus tolak
    with pytest.raises(ValueError, match="Ditolak: Ditemukan perangkat non-sim"):
        check_seed_safety(test_engine, confirm_reset=False)


def test_seed_guard_allows_non_sim_devices_with_flag():
    test_engine = get_clean_mysql_engine()

    with Session(bind=test_engine) as session:
        session.add(Device(id="esp32_device_1", name="ESP Real", mcb_watt=2200))
        session.commit()

    # Ada perangkat non-sim dengan flag confirm_reset harus diperbolehkan
    check_seed_safety(test_engine, confirm_reset=True)


def test_clean_device_guard_rejects_production_device():
    # Perangkat produksi (tanpa awalan sim- atau demo-) wajib ditolak
    with pytest.raises(ValueError, match="Penolakan perlindungan data"):
        check_clean_safety("esp32_device_1")

    with pytest.raises(ValueError, match="Penolakan perlindungan data"):
        check_clean_safety("production_meter")


def test_clean_device_deletes_only_target_demo_device():
    test_engine = get_clean_mysql_engine()

    from app.models import Reading

    with Session(bind=test_engine) as session:
        session.add(Device(id="demo-1", name="Demo 1", mcb_watt=2200))
        session.add(Device(id="sim-warung", name="Sim Warung", mcb_watt=2200))
        session.add(
            Reading(
                device_id="demo-1",
                ts=1000,
                v=220,
                i=1,
                p=220,
                e_kwh=1,
                delta_kwh=0.01,
                f=50,
                pf=1,
                rssi=-60,
            )
        )
        session.add(
            Reading(
                device_id="sim-warung",
                ts=1000,
                v=220,
                i=1,
                p=220,
                e_kwh=1,
                delta_kwh=0.01,
                f=50,
                pf=1,
                rssi=-60,
            )
        )
        session.commit()

        # Bersihkan demo-1
        res = clean_device("demo-1", session=session)
        assert res["device_deleted"] == 1
        assert res["readings"] == 1

        # Pastikan sim-warung tetap utuh dan tidak terhapus
        assert session.get(Device, "demo-1") is None
        assert session.get(Device, "sim-warung") is not None
        remaining_readings = session.query(Reading).all()
        assert len(remaining_readings) == 1
        assert remaining_readings[0].device_id == "sim-warung"
