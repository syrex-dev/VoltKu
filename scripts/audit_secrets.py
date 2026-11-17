#!/usr/bin/env python3
"""
scripts/audit_secrets.py
Membaca nilai rahasia dari .env, mencari kecocokan pada working tree dan seluruh
riwayat git, lalu melaporkan HANYA nama variabel dan jumlah kecocokan (tanpa mencetak nilai).
"""

import os
import subprocess
from pathlib import Path


def load_env_vars(env_path: Path) -> dict[str, str]:
    vars_dict = {}
    if not env_path.exists():
        return vars_dict
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                vars_dict[k] = v
    return vars_dict


def audit_secret(var_name: str, secret_val: str) -> tuple[int, int]:
    # 1. Cari di working tree
    proc_work = subprocess.run(
        ["git", "grep", "-F", secret_val],
        capture_output=True,
        text=True,
        errors="ignore",
    )
    # Filter agar tidak menghitung baris di skrip audit sendiri atau .env yang memang sumbernya
    work_matches = [
        line
        for line in proc_work.stdout.splitlines()
        if line and not line.startswith("scripts/audit_secrets.py") and not line.startswith(".env:")
    ]
    work_count = len(work_matches)

    # 2. Cari di seluruh riwayat git (git log -S)
    proc_hist = subprocess.run(
        ["git", "log", "--all", "-S", secret_val, "--oneline"],
        capture_output=True,
        text=True,
        errors="ignore",
    )
    hist_commits = [line for line in proc_hist.stdout.splitlines() if line]
    hist_count = len(hist_commits)

    return work_count, hist_count


def main() -> None:
    env_file = Path(".env")
    env_vars = load_env_vars(env_file)

    secret_keywords = ["PASS", "SECRET", "TOKEN", "KEY"]

    print("Hasil Audit Rahasia (.env vs Git Working Tree & History):")
    print(f"{'Variabel':<28} | {'Working Tree':<15} | {'Git History':<15}")
    print("-" * 64)

    total_findings = 0
    checked_count = 0

    for k, v in sorted(env_vars.items()):
        # Periksa apakah variabel merupakan rahasia
        is_secret = any(kw in k.upper() for kw in secret_keywords)
        if not is_secret:
            continue

        if not v or len(v) < 8:
            continue

        checked_count += 1
        work_cnt, hist_cnt = audit_secret(k, v)
        print(f"{k:<28} | {work_cnt:<15} | {hist_cnt:<15}")

        if work_cnt > 0 or hist_cnt > 0:
            total_findings += (work_cnt + hist_cnt)

    print("-" * 64)
    print(f"Total variabel rahasia yang diperiksa: {checked_count}")
    print(f"Total temuan kebocoran rahasia      : {total_findings}")
    if total_findings == 0:
        print("Status: BERSIH. Tidak ada nilai rahasia ditemukan di working tree atau git history.")
    else:
        print("Status: BAHAYA. Ditemukan nilai rahasia di dalam repositori!")


if __name__ == "__main__":
    main()
