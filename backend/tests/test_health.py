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
    assert settings.app_name == "VoltKu"
    assert settings.tz == "Asia/Jakarta"
    expected_default = "mysql+pymysql://root@127.0.0.1:3306/energy_monitor?charset=utf8mb4"
    assert Settings.model_fields["database_url"].default == expected_default
    assert settings.database_url.startswith("mysql+pymysql://")
