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
        jwt_secret="a_valid_jwt_secret_that_is_at_least_32_characters_long",
    )
    with pytest.raises(RuntimeError, match="Invalid DASHBOARD_PASSWORD"):
        validate_startup_credentials(s_example_pw)

    # 3. Tolak jika jwt_secret adalah contoh .env.example
    s_example_jwt = Settings(
        app_env="production",
        dashboard_password="strong_password_123",
        jwt_secret="ganti_jwt_secret_yang_panjang_dan_acak",
    )
    with pytest.raises(RuntimeError, match="Invalid JWT_SECRET"):
        validate_startup_credentials(s_example_jwt)

    # 4. Tolak jika DASHBOARD_PASSWORD < 12 karakter
    s_short_pw = Settings(
        app_env="production",
        dashboard_password="short_pw",
        jwt_secret="a_valid_jwt_secret_that_is_at_least_32_characters_long",
    )
    with pytest.raises(RuntimeError, match="at least 12 characters"):
        validate_startup_credentials(s_short_pw)

    # 5. Tolak jika JWT_SECRET < 32 karakter
    s_short_jwt = Settings(
        app_env="production",
        dashboard_password="strong_password_123",
        jwt_secret="short_jwt_secret",
    )
    with pytest.raises(RuntimeError, match="at least 32 characters"):
        validate_startup_credentials(s_short_jwt)

    # 6. Lolos jika kredensial kuat
    s_valid = Settings(
        app_env="production",
        dashboard_password="strong_password_123",
        jwt_secret="a_valid_jwt_secret_that_is_at_least_32_characters_long",
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
        {"sub": "admin"}, "wrong_secret_key_12345678901234567890", algorithm="HS256"
    )
    res_fake = client.get("/api/settings", headers={"Authorization": f"Bearer {fake_token}"})
    assert res_fake.status_code == 401

    # Token dengan alg=none (ditolak tegas)
    none_token = jwt.encode({"sub": "admin"}, "", algorithm="none")
    res_none = client.get("/api/settings", headers={"Authorization": f"Bearer {none_token}"})
    assert res_none.status_code == 401


def test_route_audit_security_lockdown():
    """Audit keamanan: /healthz, /api/login, statis publik; /api/* lain harus 401 tanpa token."""
    public_paths = {"/healthz", "/api/login"}

    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", set())
        if not path or not path.startswith("/api"):
            continue

        if path in public_paths:
            continue

        for method in methods:
            if method in ("GET", "POST", "PATCH", "PUT", "DELETE"):
                res = client.request(method, path)
                assert res.status_code == 401, (
                    f"Route {method} {path} is not secured! Expected 401, got {res.status_code}"
                )
