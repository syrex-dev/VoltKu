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


# Ambil rentang waktu sim-warung
# 3 hari 5m:
to_3d = 1794744000
from_3d = to_3d - (3 * 86400)
url_5m = (
    f"http://localhost:8000/api/devices/sim-warung/series?from={from_3d}&to={to_3d}&resolution=5m"
)

p50_5m, p95_5m, max_5m, n_5m = run_benchmark(url_5m)
print(
    f"Benchmark (a) 3 hari 5m: points={n_5m}, "
    f"p50={p50_5m:.2f} ms, p95={p95_5m:.2f} ms, max={max_5m:.2f} ms"
)

# 60 hari 1h (mengambil data hourly_stats):
to_60d = 1794744000
from_60d = to_60d - (60 * 86400)
url_1h = (
    f"http://localhost:8000/api/devices/sim-warung/series?from={from_60d}&to={to_60d}&resolution=1h"
)

p50_1h, p95_1h, max_1h, n_1h = run_benchmark(url_1h)
print(
    f"Benchmark (b) 60 hari 1h: points={n_1h}, "
    f"p50={p50_1h:.2f} ms, p95={p95_1h:.2f} ms, max={max_1h:.2f} ms"
)
