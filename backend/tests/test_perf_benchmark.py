import time

import pytest
from app.auth import create_access_token
from app.db import get_db
from app.main import app
from app.models import Base, Device, HourlyStat, Reading
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

client = TestClient(app)
auth_headers = {"Authorization": f"Bearer {create_access_token()}"}


@pytest.mark.perf
def test_benchmark_series_p95_latency():
    """Benchmark performa: Kueri series pada 14 hari raw readings (120.960 baris)

    dan 30 hari hourly stats (720 baris). Target p95 < 500 ms.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

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

    # Insert batch dalam transaksi tunggal
    session.execute(insert(Reading), raw_dicts)
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

    # 4. Jalankan kueri series 5-menit on-the-fly (rentang 3 hari) sebanyak 50 kali
    query_from = t_start + (5 * 86400)
    query_to = query_from + (3 * 86400)
    url = f"/api/devices/{device_id}/series?from={query_from}&to={query_to}&resolution=5m"

    latencies_sec = []
    n_iterations = 50

    for _ in range(n_iterations):
        t0 = time.perf_counter()
        res = client.get(url, headers=auth_headers)
        dt = time.perf_counter() - t0
        assert res.status_code == 200
        latencies_sec.append(dt)

    latencies_sec.sort()
    idx_p95 = int(0.95 * len(latencies_sec))
    p95_sec = latencies_sec[idx_p95]
    p95_ms = p95_sec * 1000.0

    print("\n[PERF BENCHMARK RESULT] 14 days raw + 30 days hourly:")
    print(f"Total readings: {n_samples}, Total hourly: {len(hourly_dicts)}")
    print(f"p95 latency: {p95_ms:.2f} ms (Target: < 500.00 ms)")

    assert p95_ms < 500.0, f"p95 latency {p95_ms:.2f} ms exceeded target 500 ms!"
    app.dependency_overrides.clear()
