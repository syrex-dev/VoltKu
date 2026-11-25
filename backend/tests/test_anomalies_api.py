import json
import time

from app.auth import create_access_token
from app.db import get_db
from app.main import app
from app.models import Anomaly
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


def test_get_anomalies_unauthorized():
    setup_test_db()
    resp = client.get("/api/anomalies")
    assert resp.status_code == 401


def test_get_anomalies_empty():
    session = setup_test_db()
    session.query(Anomaly).delete()
    session.commit()

    resp = client.get("/api/anomalies", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_anomalies_default_7_days_and_ordering():
    session = setup_test_db()
    now_ts = int(time.time())

    # Anomali 1: 1 jam lalu (dalam 7 hari)
    session.add(
        Anomaly(
            device_id="demo-1",
            ts=now_ts - 3600,
            type="power_limit",
            severity="warning",
            details_json=json.dumps({"p": 2500}),
            message="Daya melebihi batas",
            notified=1,
        )
    )
    # Anomali 2: 2 hari lalu (dalam 7 hari)
    session.add(
        Anomaly(
            device_id="demo-1",
            ts=now_ts - 172800,
            type="voltage_low",
            severity="warning",
            details_json=json.dumps({"v": 195}),
            message="Tegangan rendah",
            notified=1,
        )
    )
    # Anomali 3: 10 hari lalu (di luar 7 hari)
    session.add(
        Anomaly(
            device_id="demo-1",
            ts=now_ts - (10 * 86400),
            type="offline",
            severity="critical",
            details_json=json.dumps({"last_seen": now_ts - 10 * 86400}),
            message="Perangkat offline",
            notified=1,
        )
    )
    session.commit()

    resp = client.get("/api/anomalies", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    # Hanya 2 yang dalam 7 hari terakhir
    assert len(data) == 2
    # Terurut terbaru dulu
    assert data[0]["type"] == "power_limit"
    assert data[1]["type"] == "voltage_low"
    assert data[0]["ts"] > data[1]["ts"]
    assert data[0]["details"] == {"p": 2500}
    assert data[0]["notified"] is True

    # Jika 'from' ditentukan 15 hari lalu -> Anomali 3 juga masuk
    from_15d = now_ts - (15 * 86400)
    resp_all = client.get(f"/api/anomalies?from={from_15d}", headers=auth_headers)
    assert resp_all.status_code == 200
    assert len(resp_all.json()) == 3


def test_get_anomalies_device_filter():
    session = setup_test_db()
    now_ts = int(time.time())

    session.add(
        Anomaly(
            device_id="demo-1",
            ts=now_ts - 100,
            type="power_limit",
            severity="warning",
            details_json=json.dumps({}),
            message="Demo 1 Overload",
            notified=1,
        )
    )
    session.add(
        Anomaly(
            device_id="demo-2",
            ts=now_ts - 50,
            type="voltage_high",
            severity="warning",
            details_json=json.dumps({}),
            message="Demo 2 High Voltage",
            notified=1,
        )
    )
    session.commit()

    # Filter untuk demo-1
    resp1 = client.get("/api/anomalies?device_id=demo-1", headers=auth_headers)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert len(data1) == 1
    assert data1[0]["device_id"] == "demo-1"

    # Filter untuk demo-2
    resp2 = client.get("/api/anomalies?device_id=demo-2", headers=auth_headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2) == 1
    assert data2[0]["device_id"] == "demo-2"
