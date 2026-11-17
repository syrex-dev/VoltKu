#!/usr/bin/env python3
"""
scripts/audit_secrets.py
Membaca nilai rahasia dari .env, membandingkan dengan placeholder di .env.example.
Jika nilai sama dengan placeholder di .env.example, dilaporkan sebagai "placeholder (diabaikan)".
Jika nilai merupakan rahasia sungguhan, mencari kecocokan pada working tree dan seluruh riwayat git
HANYA melaporkan nama variabel dan jumlah kecocokan (TANPA PERNAH MENCETAK NILAI RAHASIA).

Exit code:
0 jika bersih (tidak ada rahasia nyata bocor, placeholder diabaikan)
1 jika ada temuan nyata (nilai rahasia sungguhan ditemukan di file ter-track atau riwayat)
"""

import subprocess
import sys
from pathlib import Path


def load_env_vars(env_path: Path) -> dict[str, str]:
    vars_dict: dict[str, str] = {}
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


def audit_secret(var_name: str, secret_val: str, cwd: Path = Path(".")) -> tuple[int, int]:
    # 1. Cari di working tree
    proc_work = subprocess.run(
        ["git", "grep", "-F", secret_val],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        errors="ignore",
    )
    work_matches = [
        line
        for line in proc_work.stdout.splitlines()
        if line
        and not line.startswith("scripts/audit_secrets.py")
        and not line.startswith(".env:")
    ]
    work_count = len(work_matches)

    # 2. Cari di seluruh riwayat git (git log -S)
    proc_hist = subprocess.run(
        ["git", "log", "--all", "-S", secret_val, "--oneline"],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        errors="ignore",
    )
    hist_commits = [line for line in proc_hist.stdout.splitlines() if line]
    hist_count = len(hist_commits)

    return work_count, hist_count


def run_audit(
    env_path: Path = Path(".env"),
    example_path: Path = Path(".env.example"),
    repo_path: Path = Path("."),
) -> int:
    env_vars = load_env_vars(env_path)
    example_vars = load_env_vars(example_path)
    example_values = set(example_vars.values())

    secret_keywords = ["PASS", "SECRET", "TOKEN", "KEY"]

    print("Hasil Audit Rahasia (.env vs Git Working Tree & History):")
    print(f"{'Variabel':<28} | {'Working Tree':<15} | {'Git History':<15}")
    print("-" * 64)

    total_real_findings = 0
    checked_count = 0
    placeholder_count = 0

    for k, v in sorted(env_vars.items()):
        is_secret = any(kw in k.upper() for kw in secret_keywords)
        if not is_secret:
            continue

        checked_count += 1

        # Periksa apakah nilainya merupakan placeholder dari .env.example
        is_placeholder = (v == example_vars.get(k)) or (v in example_values)
        if is_placeholder:
            placeholder_count += 1
            print(f"{k:<28} | {'placeholder (diabaikan)':<33}")
            continue

        if not v or len(v) < 8:
            print(f"{k:<28} | {'terlalu pendek (<8)':<33}")
            continue

        work_cnt, hist_cnt = audit_secret(k, v, cwd=repo_path)
        print(f"{k:<28} | {work_cnt:<15} | {hist_cnt:<15}")

        if work_cnt > 0 or hist_cnt > 0:
            total_real_findings += (work_cnt + hist_cnt)

    print("-" * 64)
    print(f"Total variabel rahasia diperiksa      : {checked_count}")
    print(f"Variabel placeholder (diabaikan)      : {placeholder_count}")
    print(f"Total temuan kebocoran rahasia nyata  : {total_real_findings}")

    if total_real_findings == 0:
        print(
            "Status: BERSIH. Tidak ada nilai rahasia nyata ditemukan "
            "di working tree atau git history."
        )
        return 0
    else:
        print("Status: BAHAYA. Ditemukan nilai rahasia sungguhan di dalam repositori!")
        return 1


def main() -> None:
    code = run_audit()
    sys.exit(code)


if __name__ == "__main__":
    main()
