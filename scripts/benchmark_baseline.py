#!/usr/bin/env python3
"""
scripts/benchmark_baseline.py
Benchmark performa agregasi kueri baseline 5 menit langsung dari tabel readings
menggunakan SQLAlchemy ORM dengan ekspresi cast(Reading.ts / 300, Integer) * 300.
"""

import statistics
import sys
import time
from pathlib import Path

# Tambahkan backend ke path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.db import SessionLocal
from app.models import Reading
from sqlalchemy import Integer, cast, func, select


def run_benchmark(device_id: str = "sim-warung", repetitions: int = 15) -> None:
    with SessionLocal() as db:
        # Tentukan rentang 14 hari penuh
        max_ts = db.scalar(select(func.max(Reading.ts)).where(Reading.device_id == device_id))
        if max_ts is None:
            print(f"Error: Perangkat {device_id} tidak memiliki data readings!")
            return

        end_ts = ((max_ts // 300) + 1) * 300
        start_ts = end_ts - (14 * 86400)

        # Hitung jumlah baris readings dalam rentang 14 hari
        total_rows = db.scalar(
            select(func.count(Reading.id)).where(
                Reading.device_id == device_id,
                Reading.ts >= start_ts,
                Reading.ts < end_ts,
            )
        )

        # Siapkan statement ORM sesuai spesifikasi
        window_expr = cast(Reading.ts / 300, Integer) * 300
        stmt = (
            select(
                window_expr.label("window_start"),
                func.count(Reading.id).label("samples"),
                func.avg(Reading.p).label("p_avg"),
                func.min(Reading.p).label("p_min"),
                func.max(Reading.p).label("p_max"),
            )
            .where(
                Reading.device_id == device_id,
                Reading.ts >= start_ts,
                Reading.ts < end_ts,
            )
            .group_by(window_expr)
            .order_by(window_expr)
        )

        print("=== BENCHMARK KUERI BASELINE 5-MENIT (14 HARI) ===")
        print(f"Device ID diukur            : {device_id}")
        print(f"Rentang Timestamp           : {start_ts} s.d. {end_ts} (14 hari = 1.209.600 detik)")
        print(f"Jumlah baris readings       : {total_rows:,} baris")

        # Pemanasan (warmup query)
        warmup_rows = db.execute(stmt).all()
        window_count = len(warmup_rows)
        print(f"Jumlah jendela 5 menit hasil: {window_count:,} jendela")
        print("-" * 55)

        # Eksekusi berulang (>= 10 ulangan)
        latencies_ms: list[float] = []
        for i in range(1, repetitions + 1):
            t0 = time.perf_counter()
            rows = db.execute(stmt).all()
            t1 = time.perf_counter()
            elapsed_ms = (t1 - t0) * 1000.0
            latencies_ms.append(elapsed_ms)
            print(f"  Ulangan {i:02d}: {elapsed_ms:6.2f} ms (baris hasil: {len(rows)})")

        min_ms = min(latencies_ms)
        max_ms = max(latencies_ms)
        avg_ms = statistics.mean(latencies_ms)
        med_ms = statistics.median(latencies_ms)

        print("-" * 55)
        print(f"Statistik Latensi ({repetitions} ulangan):")
        print(f"  Min   : {min_ms:6.2f} ms")
        print(f"  Max   : {max_ms:6.2f} ms")
        print(f"  Avg   : {avg_ms:6.2f} ms")
        print(f"  Median: {med_ms:6.2f} ms")
        print("==================================================")


if __name__ == "__main__":
    run_benchmark()
