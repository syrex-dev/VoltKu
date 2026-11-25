import time

from app.auth import create_access_token
from app.db import get_db
from app.main import app
from app.models import Device, Reading
from fastapi.testclient import TestClient
from mysql_test_helper import open_clean_test_session

client = TestClient(app)
auth_headers = {"Authorization": f"Bearer {create_access_token()}"}


def setup_test_db():
    _, session = open_clean_test_session()

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


def test_device_offline_boundary_119_and_121():
    """Uji batas persis: 119 detik tidak offline (online), 121 detik offline."""
    session = setup_test_db()
    now = int(time.time())

    # dev_119s: last seen 119 detik lalu -> TIDAK offline (online)
    dev_119 = Device(
        id="dev_119",
        name="Dev 119s",
        mcb_watt=2200,
        last_seen_at=now - 119,
        status="online",
    )
    # dev_121s: last seen 121 detik lalu -> offline
    dev_121 = Device(
        id="dev_121",
        name="Dev 121s",
        mcb_watt=2200,
        last_seen_at=now - 121,
        status="online",
    )

    session.add_all([dev_119, dev_121])
    session.commit()

    res = client.get("/api/devices", headers=auth_headers)
    assert res.status_code == 200
    devices = res.json()
    dev_map = {d["id"]: d["status"] for d in devices}

    assert dev_map["dev_119"] == "online", "119 detik tidak boleh offline"
    assert dev_map["dev_121"] == "offline", "121 detik harus offline"

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


def test_list_devices_include_latest():
    session = setup_test_db()
    now = int(time.time())
    d1 = Device(
        id="dev_inc",
        name="Panel Utama",
        location="Ruang Tamu",
        mcb_watt=2200,
        last_seen_at=now - 5,
        status="online",
    )
    d2 = Device(id="dev_empty", name="Gudang", location="Belakang", mcb_watt=1300, status="offline")
    r1 = Reading(
        device_id="dev_inc",
        ts=now - 5,
        v=222.4,
        i=2.1,
        p=450.5,
        e_kwh=15.0,
        delta_kwh=0.01,
        f=50.0,
        pf=0.96,
        rssi=-55,
    )
    session.add_all([d1, d2, r1])
    session.commit()

    res = client.get("/api/devices?include_latest=true", headers=auth_headers)
    assert res.status_code == 200
    by_id = {d["id"]: d for d in res.json()}
    assert by_id["dev_inc"]["latest"]["p"] == 450.5
    assert by_id["dev_inc"]["latest"]["v"] == 222.4
    assert by_id["dev_empty"]["latest"] is None

    app.dependency_overrides.clear()


def test_create_claim_update_delete_device():
    session = setup_test_db()
    now = int(time.time())

    # 1. Create baru (201)
    res_create = client.post(
        "/api/devices",
        headers=auth_headers,
        json={
            "id": "ML-A1B2C3",
            "name": "Meteran Utama",
            "location": "Panel Utama",
            "mcb_watt": 2200,
        },
    )
    assert res_create.status_code == 201
    created = res_create.json()
    assert created["id"] == "ML-A1B2C3"
    assert created["name"] == "Meteran Utama"
    assert created["location"] == "Panel Utama"
    assert created["mcb_watt"] == 2200
    assert created["status"] == "offline"

    # 2. Duplicate tanpa claim=true -> 409
    res_dup = client.post(
        "/api/devices",
        headers=auth_headers,
        json={"id": "ML-A1B2C3", "name": "Nama Lain", "mcb_watt": 1300},
    )
    assert res_dup.status_code == 409

    # 3. Duplicate dengan claim=true -> 200 dan metadata terupdate (status/last_seen terjaga)
    dev_row = session.get(Device, "ML-A1B2C3")
    dev_row.status = "online"
    dev_row.last_seen_at = now - 3
    session.commit()

    res_claim = client.post(
        "/api/devices",
        headers=auth_headers,
        json={
            "id": "ML-A1B2C3",
            "name": "Panel Lantai 1",
            "location": "Ruang Keluarga",
            "mcb_watt": 3500,
            "claim": True,
        },
    )
    assert res_claim.status_code == 200
    claimed = res_claim.json()
    assert claimed["name"] == "Panel Lantai 1"
    assert claimed["location"] == "Ruang Keluarga"
    assert claimed["mcb_watt"] == 3500
    assert claimed["status"] == "online"

    # 4. PATCH device
    res_patch = client.patch(
        "/api/devices/ML-A1B2C3",
        headers=auth_headers,
        json={"name": "Panel Dapur", "location": "Dapur", "mcb_watt": 1300},
    )
    assert res_patch.status_code == 200
    patched = res_patch.json()
    assert patched["name"] == "Panel Dapur"
    assert patched["location"] == "Dapur"
    assert patched["mcb_watt"] == 1300

    # 5. Validation errors -> 422
    assert (
        client.post(
            "/api/devices",
            headers=auth_headers,
            json={"id": "bad id!", "name": "X", "mcb_watt": 2200},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/devices",
            headers=auth_headers,
            json={"id": "valid_id", "name": "X", "mcb_watt": 50},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/devices/ML-A1B2C3",
            headers=auth_headers,
            json={"name": "   "},
        ).status_code
        == 422
    )

    # 6. DELETE device membersihkan relasi & mengembalikan 404 sesudahnya
    session.add(
        Reading(
            device_id="ML-A1B2C3",
            ts=now - 5,
            v=220.0,
            i=1.0,
            p=220.0,
            e_kwh=1.0,
            delta_kwh=0.0,
            f=50.0,
            pf=1.0,
            rssi=-60,
        )
    )
    session.commit()

    res_del = client.delete("/api/devices/ML-A1B2C3", headers=auth_headers)
    assert res_del.status_code == 200
    assert res_del.json() == {"deleted": True, "id": "ML-A1B2C3"}
    assert session.query(Reading).filter_by(device_id="ML-A1B2C3").count() == 0
    assert client.delete("/api/devices/ML-A1B2C3", headers=auth_headers).status_code == 404

    app.dependency_overrides.clear()
