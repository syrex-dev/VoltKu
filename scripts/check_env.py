#!/usr/bin/env python3
"""
scripts/check_env.py
Memeriksa kehadiran, panjang variabel lingkungan, dan kepatuhan aturan konfigurasi
tanpa mencetak nilai/rahasia sensitif.
"""

import os
from pathlib import Path

REQUIRED_VARS = [
    "TZ",
    "APP_ENV",
    "HOST",
    "PORT",
    "DATABASE_URL",
    "MQTT_HOST",
    "MQTT_PORT",
    "MQTT_USER",
    "MQTT_PASS",
    "DASHBOARD_PASSWORD",
    "JWT_SECRET",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_ALLOWED_CHAT_IDS",
]

PLACEHOLDER_ALLOWLIST = "123456789,987654321"
EXAMPLE_PASSWORDS = {"ganti_password_dashboard", "rahasia123", "password", ""}
COMMON_WORDS = ["password", "admin", "12345", "qwerty"]


def load_env_file(path: Path) -> dict[str, str]:
    env_vars: dict[str, str] = {}
    if not path.exists():
        return env_vars
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                env_vars[k] = v
    return env_vars


def check_dashboard_password(password: str | None, app_env: str) -> tuple[bool, str]:
    if not password:
        return False, "Kosong"
    if password in EXAMPLE_PASSWORDS:
        return False, "Cocok dengan contoh template"
    if len(password) < 12:
        return False, "Panjang kurang dari 12 karakter"
    if app_env == "production":
        lower = password.lower()
        for w in COMMON_WORDS:
            if w in lower:
                return False, f"Mengandung kata umum '{w}' (ditolak di production)"
    return True, "Lolos aturan"


def main() -> None:
    env_file = Path(".env")
    file_vars = load_env_file(env_file)

    def get_var(k: str) -> str | None:
        v = os.environ.get(k)
        if v is None:
            v = file_vars.get(k)
        return v

    app_env = get_var("APP_ENV") or "development"
    notifier_val = get_var("NOTIFIER") or "(tidak diatur / default NullNotifier)"
    chat_ids = (get_var("TELEGRAM_ALLOWED_CHAT_IDS") or "").strip()
    dash_pass = get_var("DASHBOARD_PASSWORD")

    print(f"Pemeriksaan Lingkungan (.env ada: {'Ya' if env_file.exists() else 'Tidak'}):")
    print(f"{'Variabel':<30} | {'Status':<12} | {'Panjang':<10}")
    print("-" * 58)

    all_ok = True
    for var in REQUIRED_VARS:
        val = get_var(var)
        status = "ADA" if val is not None and len(val) > 0 else "TIDAK ADA / KOSONG"
        length = len(val) if val is not None else 0

        # Wajib minimal: DASHBOARD_PASSWORD (>=12), JWT_SECRET (>=32), MQTT, DB
        if var in ("DASHBOARD_PASSWORD", "JWT_SECRET", "DATABASE_URL") and length == 0:
            all_ok = False

        print(f"{var:<30} | {status:<12} | {length:<10}")

    print("-" * 58)

    # Laporan Nilai Non-Rahasia
    print("\nInformasi Konfigurasi Tambahan:")
    print(f"  APP_ENV                                : {app_env}")
    print(f"  NOTIFIER                               : {notifier_val}")

    # Laporan Placeholder TELEGRAM_ALLOWED_CHAT_IDS
    is_placeholder_allowlist = (chat_ids == PLACEHOLDER_ALLOWLIST)
    status_ph = "Ya" if is_placeholder_allowlist else "Tidak"
    print(f"  TELEGRAM_ALLOWED_CHAT_IDS placeholder? : {status_ph}")

    # Laporan Kepatuhan DASHBOARD_PASSWORD
    pass_ok, pass_reason = check_dashboard_password(dash_pass, app_env)
    status_pw = "Ya" if pass_ok else f"Tidak ({pass_reason})"
    print(f"  DASHBOARD_PASSWORD lolos aturan?       : {status_pw}")

    print("-" * 58)
    if all_ok:
        print("Status: Variabel inti terdefinisi.")
    else:
        print("Status: Terdapat variabel inti yang kosong.")


if __name__ == "__main__":
    main()
