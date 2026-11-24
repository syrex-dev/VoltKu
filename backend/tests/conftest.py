import os

import pytest

# Pastikan seluruh tes berjalan di database in-memory sementara, bukan di data/energy.db
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["APP_ENV"] = "test"
os.environ["JWT_SECRET"] = "test_jwt_secret_at_least_32_chars_1234567890"  # gitleaks:allow
os.environ["DASHBOARD_PASSWORD"] = "test_password_12chars"


@pytest.fixture(autouse=True)
def isolate_db(monkeypatch):
    from app.config import get_settings
    from app.db import init_db
    from app.main import app

    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv(
        "JWT_SECRET", "test_jwt_secret_at_least_32_chars_1234567890"  # gitleaks:allow
    )
    monkeypatch.setenv("DASHBOARD_PASSWORD", "test_password_12chars")
    init_db()
    yield
    app.dependency_overrides.clear()
