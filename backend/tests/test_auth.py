import time
from datetime import timedelta

import jwt
import pytest
from app.auth import create_access_token, login_limiter
from app.config import Settings, validate_startup_credentials
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_login_success():
    login_limiter.reset()
    res = client.post("/api/login", json={"password": "test_password_12chars"})
    assert res.status_code == 200
    data = res.json()
    assert "token" in data
    assert data["token_type"] == "bearer"


def test_login_failure_and_rate_limiting():
    login_limiter.reset()

    # 5 percobaan gagal pertama
    for _ in range(5):
        res = client.post("/api/login", json={"password": "wrong_password"})
        assert res.status_code == 401

    # Percobaan ke-6 langsung menghasilkan HTTP 429 cepat tanpa sleep
    t0 = time.time()
    res6 = client.post("/api/login", json={"password": "wrong_password"})
    elapsed = time.time() - t0
    assert elapsed < 0.5  # Harus cepat tanpa sleep
    assert res6.status_code == 429
    assert "Retry-After" in res6.headers
    retry_after = int(res6.headers["Retry-After"])
    assert 1 <= retry_after <= 30

    # Reset limiter dan verifikasi login benar berhasil
    login_limiter.reset()
    res_ok = client.post("/api/login", json={"password": "test_password_12chars"})
    assert res_ok.status_code == 200


def test_startup_validation_rejects_insecure_secrets():
    # 1. Tolak jika kosong
    s_empty = Settings(app_env="production", dashboard_password="", jwt_secret="")
    with pytest.raises(RuntimeError, match="Invalid DASHBOARD_PASSWORD"):
        validate_startup_credentials(s_empty)

    # 2. Tolak jika password adalah contoh .env.example
    s_example_pw = Settings(
        app_env="production",
        dashboard_password="ganti_password_dashboard",
        jwt_secret="a_valid_jwt_secret_that_is_at_least_32_characters_long",  # gitleaks:allow
    )
    with pytest.raises(RuntimeError, match="Invalid DASHBOARD_PASSWORD"):
        validate_startup_credentials(s_example_pw)

    # 3. Tolak jika jwt_secret adalah contoh .env.example
    s_example_jwt = Settings(
        app_env="production",
        dashboard_password="kunci_akses_sangat_kuat_2026",  # gitleaks:allow
        jwt_secret="ganti_jwt_secret_yang_panjang_dan_acak",  # gitleaks:allow
    )
    with pytest.raises(RuntimeError, match="Invalid JWT_SECRET"):
        validate_startup_credentials(s_example_jwt)

    # 4. Tolak jika DASHBOARD_PASSWORD < 12 karakter
    s_short_pw = Settings(
        app_env="production",
        dashboard_password="short_pw",
        jwt_secret="a_valid_jwt_secret_that_is_at_least_32_characters_long",  # gitleaks:allow
    )
    with pytest.raises(RuntimeError, match="at least 12 characters"):
        validate_startup_credentials(s_short_pw)

    # 5. Tolak jika JWT_SECRET < 32 karakter
    s_short_jwt = Settings(
        app_env="production",
        dashboard_password="kunci_akses_sangat_kuat_2026",  # gitleaks:allow
        jwt_secret="short_jwt_secret",
    )
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        validate_startup_credentials(s_short_jwt)

    # 6. Tolak jika DASHBOARD_PASSWORD < 16 karakter di production
    s_short_prod = Settings(
        app_env="production",
        dashboard_password="short_secret_15",  # 15 chars
        jwt_secret="a_valid_jwt_secret_that_is_at_least_32_characters_long",  # gitleaks:allow
    )
    with pytest.raises(RuntimeError, match="at least 16 characters"):
        validate_startup_credentials(s_short_prod)

    # 7. Tolak "password12345" di production secara spesifik
    s_pwd12345 = Settings(
        app_env="production",
        dashboard_password="password12345",
        jwt_secret="a_valid_jwt_secret_that_is_at_least_32_characters_long",  # gitleaks:allow
    )
    with pytest.raises(RuntimeError, match="must be at least 16 characters"):
        validate_startup_credentials(s_pwd12345)

    # 8. Tolak jika DASHBOARD_PASSWORD mengandung kata umum di production (case-insensitive)
    for word in ("password", "admin", "12345", "qwerty", "letmein", "welcome"):
        s_common = Settings(
            app_env="production",
            dashboard_password=f"super_{word.upper()}_rahasia_aman_2026",  # gitleaks:allow
            jwt_secret="a_valid_jwt_secret_that_is_at_least_32_characters_long",  # gitleaks:allow
        )
        with pytest.raises(RuntimeError, match="must not contain common words"):
            validate_startup_credentials(s_common)

    # 9. Peringatan keras jika DASHBOARD_PASSWORD mengandung kata umum di development
    s_dev_common = Settings(
        app_env="development",
        dashboard_password="dev_password12345",
        jwt_secret="a_valid_jwt_secret_that_is_at_least_32_characters_long",  # gitleaks:allow
    )
    with pytest.MonkeyPatch().context() as mp:
        import logging

        dev_records = []

        def dev_warn(self, msg, *args):
            dev_records.append(msg % args if args else msg)

        mp.setattr(logging.Logger, "warning", dev_warn)
        validate_startup_credentials(s_dev_common)
        assert any("PERINGATAN KERAS" in r for r in dev_records)

    # 10. Peringatan log jika allowlist Telegram memakai placeholder contoh
    s_placeholder = Settings(
        app_env="production",
        dashboard_password="kunci_akses_sangat_kuat_2026",  # gitleaks:allow
        jwt_secret="a_valid_jwt_secret_that_is_at_least_32_characters_long",  # gitleaks:allow
        telegram_allowed_chat_ids="123456789,987654321",
    )
    with pytest.MonkeyPatch().context() as mp:
        import logging

        records = []

        def custom_warn(self, msg, *args):
            records.append(msg % args if args else msg)

        mp.setattr(logging.Logger, "warning", custom_warn)
        validate_startup_credentials(s_placeholder)
        assert any("placeholder" in r for r in records)

    # 8. Lolos jika kredensial kuat
    s_valid = Settings(
        app_env="production",
        dashboard_password="kunci_akses_sangat_kuat_2026",  # gitleaks:allow
        jwt_secret="a_valid_jwt_secret_that_is_at_least_32_characters_long",  # gitleaks:allow
        telegram_allowed_chat_ids="77889900",
    )
    validate_startup_credentials(s_valid)  # Tidak raise error


def test_jwt_token_validation_and_tampering():
    # Token valid
    valid_token = create_access_token()
    res = client.get("/api/settings", headers={"Authorization": f"Bearer {valid_token}"})
    assert res.status_code == 200

    # Token kedaluwarsa
    expired_token = create_access_token(expires_delta=timedelta(seconds=-10))
    res_exp = client.get("/api/settings", headers={"Authorization": f"Bearer {expired_token}"})
    assert res_exp.status_code == 401

    # Token dengan secret salah
    fake_token = jwt.encode(
        {"sub": "admin"},
        "wrong_secret_key_12345678901234567890",  # gitleaks:allow
        algorithm="HS256",
    )
    res_fake = client.get("/api/settings", headers={"Authorization": f"Bearer {fake_token}"})
    assert res_fake.status_code == 401

    # Token dengan alg=none (ditolak tegas)
    none_token = jwt.encode({"sub": "admin"}, "", algorithm="none")
    res_none = client.get("/api/settings", headers={"Authorization": f"Bearer {none_token}"})
    assert res_none.status_code == 401


def test_route_audit_security_lockdown():
    """Audit keamanan: endpoint privat dan seluruh mutasi wajib 401 tanpa token."""
    public_post_paths = {
        "/api/login",
        "/api/users/register",
        "/api/users/login",
        "/api/users/google",
        "/api/users/forgot-password",
        "/api/users/reset-password",
        "/api/admin/login",
        "/api/public/terms-consent",
    }
    public_get_paths = {
        "/healthz",
        "/api/users/oauth-config",
        "/api/users/reset-password/status",
        "/api/public/access",
        "/api/public/app-config",
        "/api/public/devices",
        "/api/public/devices/{device_id}/latest",
        "/api/public/devices/{device_id}/series",
        "/api/public/devices/{device_id}/summary",
        "/api/public/devices/{device_id}/forecast",
        "/api/public/devices/{device_id}/export",
        "/api/public/anomalies",
        "/api/public/settings",
        "/api/public/plans",
        "/api/public/payment-methods",
        "/api/payment-methods/{method_id}/qris",
    }

    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", set())
        if not path or not path.startswith("/api"):
            continue

        if path in public_post_paths:
            continue

        for method in methods:
            if path in public_get_paths and method == "GET":
                continue
            if method in ("GET", "POST", "PATCH", "PUT", "DELETE"):
                res = client.request(method, path)
                assert res.status_code == 401, (
                    f"Route {method} {path} is not secured! Expected 401, got {res.status_code}"
                )


def test_dashboard_password_password12345_is_rejected():
    """Memverifikasi bahwa 'password12345' ditolak di production dan memicu PERINGATAN di dev."""
    # 1. Startup production: ditolak tegas dengan RuntimeError
    s_prod = Settings(
        app_env="production",
        dashboard_password="password12345",
        jwt_secret="a_valid_jwt_secret_that_is_at_least_32_characters_long",  # gitleaks:allow
    )
    with pytest.raises(RuntimeError) as exc_info:
        validate_startup_credentials(s_prod)
    err = str(exc_info.value)
    assert "at least 16 characters" in err
    assert "must not contain common words" in err

    # 2. Skrip check_env.py: ditolak di production, PERINGATAN di development
    from scripts.check_env import check_dashboard_password

    ok_prod, reason_prod = check_dashboard_password("password12345", "production")
    assert not ok_prod
    assert "panjang kurang dari 16 karakter" in reason_prod
    assert "mengandung kata umum" in reason_prod

    ok_dev, reason_dev = check_dashboard_password("password12345", "development")
    assert ok_dev
    assert reason_dev.startswith("PERINGATAN")
    assert "panjang < 16 karakter" in reason_dev
    assert "kata umum" in reason_dev

