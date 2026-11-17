import logging
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # App Settings
    app_name: str = "Monitor Listrik Pintar"
    app_env: str = "production"
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

    # M3 Flags & Konfigurasi
    scheduler_enabled: bool = True
    bot_enabled: bool = True
    notifier: str = ""
    recording_notifier: bool = False
    alert_exclude_device_prefixes: str = "sim-"

    # Konstanta Tegangan (Bukan di DB settings)
    voltage_min_v: float = 200.0
    voltage_max_v: float = 240.0
    voltage_recovery_min_v: float = 205.0
    voltage_recovery_max_v: float = 235.0

    @property
    def is_scheduler_active(self) -> bool:
        if self.app_env == "test":
            return False
        return self.scheduler_enabled

    @property
    def is_bot_active(self) -> bool:
        if self.app_env == "test":
            return False
        return self.bot_enabled and bool(
            self.telegram_bot_token and self.telegram_bot_token.strip()
        )

    @property
    def allowed_chat_id_list(self) -> list[int]:
        res: list[int] = []
        for x in self.telegram_allowed_chat_ids.split(","):
            x = x.strip()
            if x:
                try:
                    res.append(int(x))
                except ValueError:
                    pass
        return res

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


def validate_startup_credentials(settings: Settings) -> None:
    """Validasi ketat kredensial saat backend start."""
    if settings.app_env == "test":
        return

    example_dash_pass = {"ganti_password_dashboard", "rahasia123", "password", ""}
    example_jwt_sec = {
        "ganti_jwt_secret_yang_panjang_dan_acak",
        "ganti-dengan-secret-acak",
        "",
    }

    dash_pass = settings.dashboard_password or ""
    jwt_sec = settings.jwt_secret or ""

    if not dash_pass or dash_pass in example_dash_pass or len(dash_pass) < 12:
        raise RuntimeError(
            "Invalid DASHBOARD_PASSWORD: must not be empty, must not match example values, "
            "and must be at least 12 characters."
        )

    common_words = ["password", "admin", "12345", "qwerty", "letmein", "welcome"]
    matched_common = [w for w in common_words if w in dash_pass.lower()]

    if settings.app_env == "production":
        if len(dash_pass) < 16 or matched_common:
            reasons = []
            if len(dash_pass) < 16:
                reasons.append("must be at least 16 characters")
            if matched_common:
                found_str = ", ".join(matched_common)
                reasons.append(
                    f"must not contain common words ({', '.join(common_words)}). Found: {found_str}"
                )
            raise RuntimeError(f"Invalid DASHBOARD_PASSWORD: in production, {'; '.join(reasons)}.")
    else:
        if matched_common:
            logger.warning(
                "PERINGATAN KERAS: DASHBOARD_PASSWORD mengandung kata umum (%s). "
                "Ganti sebelum deploy ke production!",
                ", ".join(matched_common),
            )

    placeholder_allowlist = "123456789,987654321"
    if settings.telegram_allowed_chat_ids.strip() == placeholder_allowlist:
        logger.warning(
            "TELEGRAM_ALLOWED_CHAT_IDS menggunakan nilai placeholder contoh (%s). "
            "Pesan bot tidak akan sampai ke pemilik asli!",
            placeholder_allowlist,
        )

    if not jwt_sec or jwt_sec in example_jwt_sec or len(jwt_sec) < 32:
        raise RuntimeError(
            "Invalid JWT_SECRET: must not be empty, must not match example values, "
            "and must be at least 32 characters."
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
