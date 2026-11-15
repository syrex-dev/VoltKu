import pytest
from app.models import Base, Device
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from scripts.seed_db import check_seed_safety


def test_seed_guard_allows_empty_database():
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)

    # Database kosong harus boleh tanpa flag
    check_seed_safety(test_engine, confirm_reset=False)


def test_seed_guard_allows_only_sim_devices():
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)

    with Session(bind=test_engine) as session:
        session.add(Device(id="sim-warung", name="Warung", mcb_watt=2200))
        session.add(Device(id="sim-bench", name="Bench", mcb_watt=2200))
        session.commit()

    # Hanya perangkat sim- harus boleh tanpa flag
    check_seed_safety(test_engine, confirm_reset=False)


def test_seed_guard_rejects_non_sim_devices_without_flag():
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)

    with Session(bind=test_engine) as session:
        session.add(Device(id="sim-warung", name="Warung", mcb_watt=2200))
        session.add(Device(id="esp32_device_1", name="ESP Real", mcb_watt=2200))
        session.commit()

    # Ada perangkat non-sim tanpa flag confirm_reset harus tolak
    with pytest.raises(ValueError, match="Ditolak: Ditemukan perangkat non-sim"):
        check_seed_safety(test_engine, confirm_reset=False)


def test_seed_guard_allows_non_sim_devices_with_flag():
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)

    with Session(bind=test_engine) as session:
        session.add(Device(id="esp32_device_1", name="ESP Real", mcb_watt=2200))
        session.commit()

    # Ada perangkat non-sim dengan flag confirm_reset harus diperbolehkan
    check_seed_safety(test_engine, confirm_reset=True)
