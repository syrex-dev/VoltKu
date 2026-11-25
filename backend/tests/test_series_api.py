import time

from app.auth import create_access_token
from app.db import get_db
from app.main import app
from app.models import DailyStat, Device, HourlyStat, Reading
from fastapi.testclient import TestClient
from mysql_test_helper import open_clean_test_session

client = TestClient(app)
auth_headers = {"Authorization": f"Bearer {create_access_token()}"}


def setup_series_db():
    _, session = open_clean_test_session()

    session.add(Device(id="esp_series", name="Series Test", mcb_watt=2200, status="online"))
    session.commit()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return session


def test_series_resolution_boundaries_and_types():
    session = setup_series_db()
    t_now = int(time.time())

    # 1. Rentang <= 5 jam -> raw 10s (interval_seconds = 10)
    # Tambah 5 reading
    for i in range(5):
        session.add(
            Reading(
                device_id="esp_series",
                ts=t_now - 3600 + (i * 10),
                v=220.0,
                i=1.0,
                p=220.0,
                e_kwh=10.0 + (i * 0.001),
                delta_kwh=0.001,
                f=50.0,
                pf=1.0,
                rssi=-60,
            )
        )
    session.commit()

    res_raw = client.get(
        f"/api/devices/esp_series/series?from={t_now - 4 * 3600}&to={t_now}",
        headers=auth_headers,
    )
    assert res_raw.status_code == 200
    d_raw = res_raw.json()
    assert d_raw["interval_seconds"] == 10
    assert len(d_raw["points"]) == 5
    assert isinstance(d_raw["points"][0]["ts"], int)
    assert d_raw["points"][0]["v"] is not None

    # 2. Rentang > 5 jam s.d. 3 hari -> 5 menit on-the-fly (interval_seconds = 300)
    res_5m = client.get(
        f"/api/devices/esp_series/series?from={t_now - 2 * 86400}&to={t_now}",
        headers=auth_headers,
    )
    assert res_5m.status_code == 200
    d_5m = res_5m.json()
    assert d_5m["interval_seconds"] == 300
    assert isinstance(d_5m["points"][0]["ts"], int)

    # 3. Rentang > 3 hari s.d. 60 hari -> 1 jam (interval_seconds = 3600, v=null)
    session.add(
        HourlyStat(
            device_id="esp_series",
            hour_start=t_now - 10 * 86400,
            kwh=0.5,
            p_avg=500.0,
            p_max=800.0,
            p_min=200.0,
            samples=360,
        )
    )
    session.commit()

    res_1h = client.get(
        f"/api/devices/esp_series/series?from={t_now - 15 * 86400}&to={t_now}",
        headers=auth_headers,
    )
    assert res_1h.status_code == 200
    d_1h = res_1h.json()
    assert d_1h["interval_seconds"] == 3600
    assert len(d_1h["points"]) >= 1
    assert d_1h["points"][0]["v"] is None
    assert isinstance(d_1h["points"][0]["ts"], int)

    # 4. Rentang > 60 hari -> 1 hari (interval_seconds = 86400, v=null)
    session.add(
        DailyStat(
            device_id="esp_series",
            day="2026-08-01",
            kwh=10.0,
            cost_rp=14447,
            tariff_sen=144470,
            p_max=1000.0,
            p_base=150.0,
        )
    )
    session.commit()

    res_1d = client.get(
        "/api/devices/esp_series/series?from=1780000000&to=1794700000",
        headers=auth_headers,
    )
    assert res_1d.status_code == 200
    d_1d = res_1d.json()
    assert d_1d["interval_seconds"] == 86400
    assert d_1d["points"][0]["v"] is None
    assert isinstance(d_1d["points"][0]["ts"], int)

    app.dependency_overrides.clear()


def test_series_truncation_flag():
    session = setup_series_db()
    t_start = 1736000000
    # Masukkan 2100 readings
    readings = []
    for i in range(2100):
        readings.append(
            Reading(
                device_id="esp_series",
                ts=t_start + (i * 5),
                v=220.0,
                i=1.0,
                p=220.0,
                e_kwh=10.0,
                delta_kwh=0.001,
                f=50.0,
                pf=1.0,
                rssi=-60,
            )
        )
    session.add_all(readings)
    session.commit()

    res = client.get(
        f"/api/devices/esp_series/series?from={t_start}&to={t_start + 2100 * 5}&resolution=raw",
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["truncated"] is True
    assert len(data["points"]) == 2000  # Dipotong tepat di 2000 titik

    app.dependency_overrides.clear()


def test_series_validation_errors():
    setup_series_db()

    # 1. from > to -> 422
    res1 = client.get(
        "/api/devices/esp_series/series?from=1700002000&to=1700001000", headers=auth_headers
    )
    assert res1.status_code == 422

    # 2. Rentang > 366 hari -> 422
    res2 = client.get(
        f"/api/devices/esp_series/series?from=1700000000&to={1700000000 + (367 * 86400)}",
        headers=auth_headers,
    )
    assert res2.status_code == 422

    app.dependency_overrides.clear()


def test_series_explicit_resolution_caps_and_truncates():
    session = setup_series_db()
    t_start = 1736000000

    # Buat 2500 readings untuk menguji resolusi eksplisit raw
    readings = [
        Reading(
            device_id="esp_series",
            ts=t_start + (i * 10),
            v=220.0,
            i=1.0,
            p=220.0,
            e_kwh=10.0 + (i * 0.001),
            delta_kwh=0.001,
            f=50.0,
            pf=1.0,
            rssi=-60,
        )
        for i in range(2500)
    ]
    session.add_all(readings)
    session.commit()

    # Minta explicit resolution=raw
    res = client.get(
        f"/api/devices/esp_series/series?from={t_start}&to={t_start + (2500 * 10)}&resolution=raw",
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["truncated"] is True
    assert len(data["points"]) == 2000  # Dipotong di 2000 titik, tidak mengembalikan 2500

    app.dependency_overrides.clear()
