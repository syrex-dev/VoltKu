import time

from app.auth import create_access_token
from app.db import get_db
from app.main import app
from app.models import Base, Device, Reading
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

client = TestClient(app)
auth_headers = {"Authorization": f"Bearer {create_access_token()}"}


def setup_test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return session


def test_get_devices_status_dynamic():
    session = setup_test_db()
    now = int(time.time())

    # Device 1: baru online 20 detik lalu -> "online"
    d1 = Device(id="dev_1", name="Dev 1", mcb_watt=2200, last_seen_at=now - 20, status="online")
    # Device 2: timeout 150 detik lalu -> "offline"
    d2 = Device(id="dev_2", name="Dev 2", mcb_watt=1300, last_seen_at=now - 150, status="online")
    # Device 3: status eksplisit offline (LWT) -> "offline"
    d3 = Device(id="dev_3", name="Dev 3", mcb_watt=3500, last_seen_at=now - 10, status="offline")

    session.add_all([d1, d2, d3])
    session.commit()

    res = client.get("/api/devices", headers=auth_headers)
    assert res.status_code == 200
    devices = res.json()
    assert len(devices) == 3

    dev_map = {d["id"]: d["status"] for d in devices}
    assert dev_map["dev_1"] == "online"
    assert dev_map["dev_2"] == "offline"
    assert dev_map["dev_3"] == "offline"

    app.dependency_overrides.clear()


def test_get_device_latest_reading():
    session = setup_test_db()
    now = int(time.time())

    dev = Device(id="d_latest", name="D Latest", mcb_watt=2200, status="online")
    r1 = Reading(
        device_id="d_latest",
        ts=now - 20,
        v=220.0,
        i=1.0,
        p=220.0,
        e_kwh=10.0,
        delta_kwh=0.0,
        f=50.0,
        pf=1.0,
        rssi=-60,
    )
    r2 = Reading(
        device_id="d_latest",
        ts=now - 10,
        v=221.0,
        i=1.5,
        p=331.5,
        e_kwh=10.005,
        delta_kwh=0.005,
        f=50.0,
        pf=0.99,
        rssi=-58,
    )
    session.add_all([dev, r1, r2])
    session.commit()

    # Device tidak ada -> 404
    res_not_found = client.get("/api/devices/unknown/latest", headers=auth_headers)
    assert res_not_found.status_code == 404

    # Device ada -> ambil reading r2 (ts terbaru)
    res = client.get("/api/devices/d_latest/latest", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["ts"] == now - 10
    assert data["p"] == 331.5
    assert data["e"] == 10.005
    assert data["v"] == 221.0

    app.dependency_overrides.clear()


def test_get_anomalies_empty():
    res = client.get("/api/anomalies", headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == []
