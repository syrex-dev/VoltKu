import time

import pytest
from app.auth import create_access_token
from app.db import get_db
from app.main import app
from app.models import Device, HourlyStat, Reading
from fastapi.testclient import TestClient
from mysql_test_helper import open_clean_test_session
from sqlalchemy import insert

client = TestClient(app)
auth_headers = {"Authorization": f"Bearer {create_access_token()}"}


@pytest.mark.perf
def test_benchmark_series_p95_latency():
    """Benchmark performa: Kueri series pada 14 hari raw readings (120.960 baris)

    dan 30 hari hourly stats (720 baris). Target p95 < 200 ms.
    """
    _, session = open_clean_test_session()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # 1. Registrasi device
    device_id = "esp_perf_test"
    session.add(Device(id=device_id, name="Perf Device", mcb_watt=2200, status="online"))
    session.commit()

    # 2. Buat 14 hari data mentah (120.960 baris readings, interval 10s)
    # Gunakan direct bulk insert via SQLAlchemy Core untuk kecepatan setup in-memory
    t_start = 1736000000
    n_samples = 14 * 8640  # 120.960 sampel
    raw_dicts = []
    for i in range(n_samples):
        ts_val = t_start + (i * 10)
        raw_dicts.append(
            {
                "device_id": device_id,
                "ts": ts_val,
                "v": 220.0,
                "i": 1.5,
                "p": 330.0,
                "e_kwh": 10.0 + (i * 0.0009),
                "delta_kwh": 0.0009,
                "f": 50.0,
                "pf": 0.98,
                "rssi": -60,
                "is_gap": 0,
            }
        )

    # Insert batch per chunk agar optimal di MySQL & SQLAlchemy
    chunk_size = 10000
    for start in range(0, len(raw_dicts), chunk_size):
        session.execute(insert(Reading), raw_dicts[start : start + chunk_size])
    session.commit()

    # 3. Buat 30 hari data hourly stats (720 baris)
    hourly_dicts = []
    for h in range(30 * 24):
        hourly_dicts.append(
            {
                "device_id": device_id,
                "hour_start": t_start + (h * 3600),
                "kwh": 0.33,
                "p_avg": 330.0,
                "p_max": 500.0,
                "p_min": 150.0,
                "samples": 360,
            }
        )
    session.execute(insert(HourlyStat), hourly_dicts)
    session.commit()

    # 4. Jalankan kueri series 5-menit on-the-fly (rentang 3 hari) sebanyak 35 kali
    query_from = t_start + (5 * 86400)
    query_to = query_from + (3 * 86400)
    url_5m = f"/api/devices/{device_id}/series?from={query_from}&to={query_to}&resolution=5m"

    latencies_5m = []
    for _ in range(35):
        t0 = time.perf_counter()
        res = client.get(url_5m, headers=auth_headers)
        dt = time.perf_counter() - t0
        assert res.status_code == 200
        latencies_5m.append(dt * 1000.0)

    latencies_5m.sort()
    p50_5m = latencies_5m[int(0.50 * len(latencies_5m))]
    p95_5m = latencies_5m[int(0.95 * len(latencies_5m))]
    max_5m = max(latencies_5m)

    # 5. Jalankan kueri series 1-jam (rentang 60 hari) sebanyak 35 kali
    url_1h = (
        f"/api/devices/{device_id}/series?from={t_start}&to={t_start + (60 * 86400)}&resolution=1h"
    )
    latencies_1h = []
    for _ in range(35):
        t0 = time.perf_counter()
        res = client.get(url_1h, headers=auth_headers)
        dt = time.perf_counter() - t0
        assert res.status_code == 200
        latencies_1h.append(dt * 1000.0)

    latencies_1h.sort()
    p50_1h = latencies_1h[int(0.50 * len(latencies_1h))]
    p95_1h = latencies_1h[int(0.95 * len(latencies_1h))]
    max_1h = max(latencies_1h)

    print("\n[PERF BENCHMARK RESULT]")
    print(f"(a) 3 hari 5m: p50={p50_5m:.2f} ms, p95={p95_5m:.2f} ms, max={max_5m:.2f} ms")
    print(f"(b) 60 hari 1h: p50={p50_1h:.2f} ms, p95={p95_1h:.2f} ms, max={max_1h:.2f} ms")

    assert p95_5m < 200.0, f"5m p95 {p95_5m:.2f} ms exceeded target 200 ms"
    assert p95_1h < 200.0, f"1h p95 {p95_1h:.2f} ms exceeded target 200 ms"
    app.dependency_overrides.clear()
