import os

import pytest
from mysql_test_helper import TEST_MYSQL_URL, close_active_test_sessions, get_clean_mysql_engine

# Pastikan seluruh tes berjalan di database MySQL khusus uji, bukan DB produksi
os.environ["DATABASE_URL"] = TEST_MYSQL_URL
os.environ["APP_ENV"] = "test"
os.environ["JWT_SECRET"] = "test_jwt_secret_at_least_32_chars_1234567890"  # gitleaks:allow
os.environ["DASHBOARD_PASSWORD"] = "test_password_12chars"


@pytest.fixture(autouse=True)
def isolate_db(monkeypatch, tmp_path):
    from app.auth import (
        api_burst_limiter,
        login_limiter,
        public_consent_limiter,
        register_limiter,
        user_login_limiter,
    )
    from app.config import get_settings
    from app.db import init_db
    from app.main import app

    login_limiter.reset()
    user_login_limiter.reset()
    register_limiter.reset()
    public_consent_limiter.reset()
    api_burst_limiter.reset()
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", TEST_MYSQL_URL)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv(
        "JWT_SECRET", "test_jwt_secret_at_least_32_chars_1234567890"  # gitleaks:allow
    )
    monkeypatch.setenv("DASHBOARD_PASSWORD", "test_password_12chars")
    monkeypatch.setenv("VOLTKU_STORAGE_DIR", str(tmp_path / "storage"))
    get_clean_mysql_engine()
    init_db()
    yield
    close_active_test_sessions()
    app.dependency_overrides.clear()
