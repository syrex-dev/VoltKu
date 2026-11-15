from app.config import Settings, get_settings
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_settings_load_defaults() -> None:
    settings = get_settings()
    assert settings.app_name == "Monitor Listrik Pintar"
    assert settings.tz == "Asia/Jakarta"
    # Verifikasi default field di model Settings adalah sqlite:///./data/energy.db
    assert Settings.model_fields["database_url"].default == "sqlite:///./data/energy.db"
    assert settings.database_url in ("sqlite:///./data/energy.db", "sqlite:///:memory:")
