import json
import os
import time
import urllib.request

# Baca password dari environment variable atau .env
password = os.environ.get("DASHBOARD_PASSWORD", "")
if not password:
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("DASHBOARD_PASSWORD="):
                    password = line.strip().split("=", 1)[1].strip('"').strip("'")

# 1. Login
login_req = urllib.request.Request(
    "http://localhost:8000/api/login",
    data=json.dumps({"password": password}).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(login_req) as resp:
    token = json.loads(resp.read().decode("utf-8"))["token"]

headers = {"Authorization": f"Bearer {token}"}


def calc_percentile(arr, p):
    k = (len(arr) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(arr) - 1)
    d = k - f
    return arr[f] + d * (arr[c] - arr[f])


def run_benchmark(url, n_reps=35):
    # Warmup 3 reps
    for _ in range(3):
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            resp.read()

    latencies = []
    for _ in range(n_reps):
        t0 = time.perf_counter()
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        dt_ms = (time.perf_counter() - t0) * 1000.0
        latencies.append(dt_ms)

    latencies.sort()
    p50 = float(calc_percentile(latencies, 50))
    p95 = float(calc_percentile(latencies, 95))
    p_max = float(max(latencies))
    return p50, p95, p_max, len(data.get("points", []))


# Ambil timestamp dinamis
req_w = urllib.request.Request(
    "http://localhost:8000/api/devices/sim-warung/latest", headers=headers
)
with urllib.request.urlopen(req_w) as resp:
    latest_data = json.loads(resp.read().decode("utf-8"))
    to_3d = latest_data["ts"]

from_3d = to_3d - (3 * 86400)
url_5m = (
    f"http://localhost:8000/api/devices/sim-warung/series?from={from_3d}&to={to_3d}&resolution=5m"
)

p50_5m, p95_5m, max_5m, n_5m = run_benchmark(url_5m)

# 60 hari 1h menggunakan device terpisah sim-bench
req_b = urllib.request.Request(
    "http://localhost:8000/api/devices", headers=headers
)
with urllib.request.urlopen(req_b) as resp:
    devs = json.loads(resp.read().decode("utf-8"))
    b_dev = next((d for d in devs if d["id"] == "sim-bench"), None)
    to_60d = b_dev["last_data_ts"] if b_dev and b_dev.get("last_data_ts") else to_3d

from_60d = to_60d - (60 * 86400)
url_1h = (
    f"http://localhost:8000/api/devices/sim-bench/series?from={from_60d}&to={to_60d}&resolution=1h"
)

p50_1h, p95_1h, max_1h, n_1h = run_benchmark(url_1h)

status_5m = "LOLOS" if p95_5m < 200.0 else "GAGAL"
status_1h = "LOLOS" if p95_1h < 200.0 else "GAGAL"

hdr_cols = ["Skenario", "Device", "Titik", "p50 (ms)", "p95 (ms)", "Max (ms)", "Target", "Status"]
col_fmts = ["{:<28}", "{:<10}", "{:>6}", "{:>9}", "{:>9}", "{:>9}", "{:>10}", "{:>8}"]

def fmt_row(vals):
    cells = [fmt.format(val) for fmt, val in zip(col_fmts, vals, strict=False)]
    return "| " + " | ".join(cells) + " |"

sep_parts = ["-" * 28, "-" * 10, "-" * 6, "-" * 9, "-" * 9, "-" * 9, "-" * 10, "-" * 8]
sep = "|-" + "-+-".join(sep_parts) + "-|"

print("\n=== HASIL BENCHMARK LATENSI CONTAINER (35 REPETISI) ===")
print(fmt_row(hdr_cols))
print(sep)
row_5m = [
    "(a) 3 Hari (5 Menit)",
    "sim-warung",
    n_5m,
    f"{p50_5m:.2f}",
    f"{p95_5m:.2f}",
    f"{max_5m:.2f}",
    "< 200 ms",
    status_5m,
]
row_1h = [
    "(b) 60 Hari (1 Jam)",
    "sim-bench",
    n_1h,
    f"{p50_1h:.2f}",
    f"{p95_1h:.2f}",
    f"{max_1h:.2f}",
    "< 200 ms",
    status_1h,
]
print(fmt_row(row_5m))
print(fmt_row(row_1h))
