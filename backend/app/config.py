from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Settings
    app_name: str = "Monitor Listrik Pintar"
    app_env: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    tz: str = "Asia/Jakarta"

    # Database & Perangkat
    database_url: str = "sqlite:///./data/energy.db"
    default_mcb_watt: int = 2200

    # MQTT Broker (Default non-rahasia untuk local testing)
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_user: str = "energy_backend"
    mqtt_pass: str = ""

    # Kredensial & Rahasia (Opsional di M0, diwajibkan di milestone yang memakainya)
    dashboard_password: Optional[str] = None
    jwt_secret: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_allowed_chat_ids: str = ""
    llm_provider: str = "gemini"
    llm_model: str = "gemini-1.5-flash"
    llm_api_key: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
