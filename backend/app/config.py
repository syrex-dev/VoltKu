import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # App Settings
    app_name: str = "VoltKu"
    app_env: str = "production"
    host: str = "0.0.0.0"
    port: int = 8088
    tz: str = "Asia/Jakarta"

    # Database & Perangkat
    database_url: str = "mysql+pymysql://root@127.0.0.1:3306/energy_monitor?charset=utf8mb4"
    default_mcb_watt: int = 2200

    # MQTT Broker (Default non-rahasia untuk local testing)
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_user: str = "energy_backend"
    mqtt_pass: str = ""
    mqtt_use_tls: bool = False
    mqtt_ca_cert: Optional[str] = None
    mqtt_tls_insecure: bool = False

    # Kredensial & Rahasia (Opsional di M0, diwajibkan di milestone yang memakainya)
    dashboard_password: Optional[str] = None
    jwt_secret: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_allowed_chat_ids: str = ""
    llm_provider: str = "gemini"
    llm_model: str = "gemini-3-flash-preview"
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None

    # Google Sign-In & App Terms Config (Opsional)
    google_client_id: Optional[str] = None
    google_android_client_id: Optional[str] = None
    terms_version: str = "2026-11-v1"

    # Email / SMTP Reset Kata Sandi (Opsional)
    app_public_url: str = "https://voltku.synemax.web.id"
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None
    smtp_from_email: Optional[str] = None
    smtp_from_name: str = "VoltKu"
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False

    # Firebase Cloud Messaging (FCM HTTP v1 Opsional untuk Android Push Instan)
    firebase_credentials_path: Optional[str] = None
    firebase_project_id: Optional[str] = None

    # M3 Flags & Konfigurasi
    scheduler_enabled: bool = True
    bot_enabled: bool = True
    notifier: str = ""
    recording_notifier: bool = False
    alert_exclude_device_prefixes: str = "sim-"
    public_dashboard_enabled: bool = True
    cors_allowed_origins: str = (
        "https://voltku.synemax.web.id,"
        "https://localhost,"
        "http://localhost,"
        "capacitor://localhost,"
        "http://localhost:5188,"
        "http://127.0.0.1:5188,"
        "http://localhost:8088,"
        "http://127.0.0.1:8088,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "http://127.0.0.1:8000"
    )

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
    def allowed_google_client_ids(self) -> list[str]:
        ids: list[str] = []
        for raw in (self.google_client_id, self.google_android_client_id):
            if raw and raw.strip():
                val = raw.strip()
                if val not in ids:
                    ids.append(val)
        return ids

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

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
        env_file=(str(Path(__file__).resolve().parent.parent.parent / ".env"), ".env", "../.env"),
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
