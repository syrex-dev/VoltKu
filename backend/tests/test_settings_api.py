from app.auth import create_access_token
from app.db import get_db
from app.main import app
from app.models import Setting
from fastapi.testclient import TestClient
from mysql_test_helper import open_clean_test_session

client = TestClient(app)
auth_headers = {"Authorization": f"Bearer {create_access_token()}"}


def setup_test_db():
    _, session = open_clean_test_session()

    # Seed default settings
    session.add_all(
        [
            Setting(key="tariff_sen_per_kwh", value="144470"),
            Setting(key="power_limit_w", value="2200"),
            Setting(key="alert_cooldown_min", value="30"),
            Setting(key="extra_percent", value="0.0"),
            Setting(key="report_hour", value="21"),
        ]
    )
    session.commit()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return session


def test_get_settings():
    setup_test_db()
    res = client.get("/api/settings", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["tariff_rp"] == "1444.70"
    assert data["tariff_sen"] == 144470
    assert data["power_limit_w"] == 2200
    assert data["alert_cooldown_min"] == 30
    assert data["extra_percent"] == 0.0
    assert data["report_hour"] == 21
    app.dependency_overrides.clear()


def test_patch_settings_valid_and_decimal():
    setup_test_db()
    # Update tarif dan batas daya
    res = client.patch(
        "/api/settings",
        json={"tariff_rp": "1500.50", "power_limit_w": 3500, "extra_percent": 2.5},
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["tariff_rp"] == "1500.50"
    assert data["tariff_sen"] == 150050
    assert data["power_limit_w"] == 3500
    assert data["extra_percent"] == 2.5
    app.dependency_overrides.clear()


def test_patch_settings_rejects_more_than_two_decimals():
    setup_test_db()
    # Lebih dari 2 angka desimal (1444.701) harus ditolak tegas, tidak dibulatkan diam-diam
    res = client.patch("/api/settings", json={"tariff_rp": "1444.701"}, headers=auth_headers)
    assert res.status_code == 422
    assert "at most 2 decimal places" in res.json()["error"]["message"]
    app.dependency_overrides.clear()


def test_patch_settings_rejects_nan_inf_and_out_of_bounds():
    setup_test_db()

    # Tolak NaN
    res_nan = client.patch("/api/settings", json={"tariff_rp": "NaN"}, headers=auth_headers)
    assert res_nan.status_code == 422

    # Tolak Infinity
    res_inf = client.patch("/api/settings", json={"tariff_rp": "Infinity"}, headers=auth_headers)
    assert res_inf.status_code == 422

    # Tolak tarif <= 0
    res_zero = client.patch("/api/settings", json={"tariff_rp": "0.00"}, headers=auth_headers)
    assert res_zero.status_code == 422

    # Tolak tarif > 100000
    res_high = client.patch("/api/settings", json={"tariff_rp": "100000.50"}, headers=auth_headers)
    assert res_high.status_code == 422

    # Tolak power_limit_w < 100
    res_p_low = client.patch("/api/settings", json={"power_limit_w": 50}, headers=auth_headers)
    assert res_p_low.status_code == 422

    # Tolak power_limit_w > 25000
    res_p_high = client.patch("/api/settings", json={"power_limit_w": 30000}, headers=auth_headers)
    assert res_p_high.status_code == 422

    # Tolak cooldown < 5 atau > 1440
    res_c_low = client.patch("/api/settings", json={"alert_cooldown_min": 2}, headers=auth_headers)
    assert res_c_low.status_code == 422
    res_c_high = client.patch(
        "/api/settings", json={"alert_cooldown_min": 2000}, headers=auth_headers
    )
    assert res_c_high.status_code == 422

    # Tolak report_hour di luar 0..23
    res_h_neg = client.patch("/api/settings", json={"report_hour": -1}, headers=auth_headers)
    assert res_h_neg.status_code == 422
    res_h_24 = client.patch("/api/settings", json={"report_hour": 24}, headers=auth_headers)
    assert res_h_24.status_code == 422

    # Tolak report_timezone tidak dikenal
    res_tz_bad = client.patch(
        "/api/settings", json={"report_timezone": "Mars/Olympus"}, headers=auth_headers
    )
    assert res_tz_bad.status_code == 422

    app.dependency_overrides.clear()


def test_patch_settings_supports_wita_and_wit_timezones():
    setup_test_db()
    res_default = client.get("/api/settings", headers=auth_headers)
    assert res_default.status_code == 200
    assert res_default.json()["report_timezone"] == "Asia/Jakarta"

    res_wita = client.patch(
        "/api/settings",
        json={"report_hour": 20, "report_timezone": "Asia/Makassar"},
        headers=auth_headers,
    )
    assert res_wita.status_code == 200
    assert res_wita.json()["report_hour"] == 20
    assert res_wita.json()["report_timezone"] == "Asia/Makassar"

    res_wit = client.patch(
        "/api/settings",
        json={"report_timezone": "Asia/Jayapura"},
        headers=auth_headers,
    )
    assert res_wit.status_code == 200
    assert res_wit.json()["report_timezone"] == "Asia/Jayapura"

    app.dependency_overrides.clear()
