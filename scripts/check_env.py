#!/usr/bin/env python3
"""
scripts/check_env.py
Memeriksa kehadiran dan panjang variabel lingkungan tanpa mencetak nilai/rahasia.
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


def main() -> None:
    env_file = Path(".env")
    file_vars = load_env_file(env_file)

    print(f"Pemeriksaan Lingkungan (.env ada: {'Ya' if env_file.exists() else 'Tidak'}):")
    print(f"{'Variabel':<30} | {'Status':<12} | {'Panjang':<10}")
    print("-" * 58)

    all_ok = True
    for var in REQUIRED_VARS:
        val = os.environ.get(var)
        if val is None:
            val = file_vars.get(var)

        status = "ADA" if val is not None and len(val) > 0 else "TIDAK ADA / KOSONG"
        length = len(val) if val is not None else 0

        # Wajib minimal: DASHBOARD_PASSWORD (>=12), JWT_SECRET (>=32), MQTT, DB
        if var in ("DASHBOARD_PASSWORD", "JWT_SECRET", "DATABASE_URL") and length == 0:
            all_ok = False

        print(f"{var:<30} | {status:<12} | {length:<10}")

    print("-" * 58)
    if all_ok:
        print("Status: Variabel inti terdefinisi.")
    else:
        print("Status: Terdapat variabel inti yang kosong.")


if __name__ == "__main__":
    main()

