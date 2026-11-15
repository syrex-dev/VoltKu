from fastapi.testclient import TestClient
from app.config import get_settings
from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_settings_load_defaults() -> None:
    settings = get_settings()
    assert settings.app_name == "Monitor Listrik Pintar"
    assert settings.tz == "Asia/Jakarta"
    assert settings.database_url == "sqlite:///./data/energy.db"
