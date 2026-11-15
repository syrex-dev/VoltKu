import os
import sys

sys.path.insert(0, os.path.abspath("backend"))

from app.db import SessionLocal
from app.models import DailyStat, HourlyStat, Reading
from sqlalchemy import func, select

with SessionLocal() as s:
    total_readings = s.scalar(select(func.count(Reading.id)))
    gap_readings = s.scalar(select(func.count(Reading.id)).where(Reading.is_gap == 1))
    daily_rows = s.scalars(select(DailyStat).order_by(DailyStat.day.asc())).all()
    hourly_samples_stats = s.execute(
        select(
            func.min(HourlyStat.samples),
            func.max(HourlyStat.samples),
            func.avg(HourlyStat.samples),
            func.count(HourlyStat.hour_start),
        )
    ).one()

    print("=== HASIL SEED 7 HARI ===")
    print(f"Total Readings: {total_readings}")
    print(f"Is Gap == 1 Readings: {gap_readings}")
    min_s, max_s, avg_s, h_count = hourly_samples_stats
    print(f"Hourly: {h_count} buckets | Samples/hr: Min={min_s}, Max={max_s}, Avg={avg_s:.1f}")
    print("\n=== DAILY STATS (7-8 baris) ===")
    print(
        f"| {'Day (WIB)':<10} | {'kWh':>8} | {'Cost (Rp)':>10} | "
        f"{'Tariff':>8} | {'P Max (W)':>10} | {'P Base':>8} |"
    )
    sep = "|" + "-+-".join(["-" * 10, "-" * 8, "-" * 10, "-" * 8, "-" * 10, "-" * 8]) + "|"
    print(sep)
    for d in daily_rows:
        p_base_str = f"{d.p_base:.1f}" if d.p_base is not None else "NULL"
        print(
            f"| {d.day:<10} | {d.kwh:>8.3f} | {d.cost_rp:>10} | "
            f"{d.tariff_sen:>8} | {d.p_max:>10.1f} | {p_base_str:>8} |"
        )
