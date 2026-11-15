import os

import pytest

# Pastikan seluruh tes berjalan di database in-memory sementara, bukan di data/energy.db
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["APP_ENV"] = "test"


@pytest.fixture(autouse=True)
def isolate_db(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("APP_ENV", "test")
