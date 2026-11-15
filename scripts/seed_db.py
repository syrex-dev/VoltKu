import argparse
import os
import random
import sys
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
backend_dir = os.path.join(BASE_DIR, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.db import SessionLocal, engine, init_db  # noqa: E402
from app.models import Base, DailyStat, Device, HourlyStat, Reading  # noqa: E402
from app.mqtt_ingest import process_telemetry_payload  # noqa: E402
from app.services.aggregation import update_daily_stat, update_hourly_stat  # noqa: E402

TZ_WIB = ZoneInfo("Asia/Jakarta")


def get_realistic_power(hour_wib: float) -> float:
    """Menghasilkan profil daya realistis rumah tangga/warung (Watt)."""
    if 0.0 <= hour_wib < 5.0:
        p = 140.0 + random.uniform(-15.0, 20.0)
    elif 5.0 <= hour_wib < 8.0:
        p = 450.0 + random.uniform(-40.0, 180.0)
    elif 8.0 <= hour_wib < 17.0:
        p = 350.0 + random.uniform(-30.0, 80.0)
    elif 17.0 <= hour_wib < 22.0:
        p = 850.0 + random.uniform(-60.0, 220.0)
    else:
        p = 290.0 + random.uniform(-20.0, 60.0)
    return max(80.0, min(1800.0, round(p, 1)))


def check_seed_safety(bind_engine, confirm_reset: bool) -> None:
    """Memeriksa keamanan reset database.

    Menolak reset jika terdapat perangkat tanpa awalan 'sim-' kecuali
    confirm_reset=True diberikan.
    """
    inspector = inspect(bind_engine)
    if "devices" in inspector.get_table_names():
        with Session(bind=bind_engine) as session:
            device_ids = session.scalars(select(Device.id)).all()
            non_sim = [d for d in device_ids if not d.startswith("sim-")]
            if non_sim and not confirm_reset:
                raise ValueError(
                    f"Ditolak: Ditemukan perangkat non-sim di DB: {non_sim}. "
                    "Gunakan flag --confirm-reset untuk memaksa reset."
                )


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset dan seed database energi.")
    parser.add_argument(
        "--confirm-reset",
        action="store_true",
        help="Wajib jika database memuat perangkat non-sim (bukan simulasi).",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("RESET & SEED DATABASE ENERGI (PRODUKSI & BENCHMARK)")
    print("=" * 60)

    try:
        check_seed_safety(engine, args.confirm_reset)
    except ValueError as e:
        print(f"ABORT: {e}", file=sys.stderr)
        sys.exit(1)

    # 1. Hapus tabel lama dan buat ulang secara bersih
    print("[1/5] Inisialisasi skema tabel database...")
    Base.metadata.drop_all(bind=engine)
    init_db()

    with SessionLocal() as session:
        # 2. Daftarkan perangkat
        print("[2/5] Mendaftarkan perangkat...")
        devices = [
            Device(id="sim-warung", name="Warung Kelontong", mcb_watt=2200, location="Warung"),
            Device(id="sim-bench", name="Benchmark Device 60D", mcb_watt=2200, location="Lab"),
            Device(id="demo-1", name="Perangkat Demo M3", mcb_watt=2200, location="Rumah"),
        ]
        for d in devices:
            session.add(d)
        session.commit()

        # 3. Seeding sim-warung (14 hari raw readings ~120.960 sampel)
        print("[3/5] Seeding sim-warung: 14 hari raw telemetry readings (interval 10s)...")
        now_ts = int(datetime.now(timezone.utc).timestamp())
        now_ts = (now_ts // 10) * 10
        start_ts = now_ts - (14 * 86400)
        total_samples = (now_ts - start_ts) // 10

        curr_e = 100.0
        touched_hours: set[int] = set()
        touched_sample_timestamps: list[int] = []
        t0 = time.time()
        inserted_count = 0

        for ts in range(start_ts, now_ts, 10):
            dt_wib = datetime.fromtimestamp(ts, tz=TZ_WIB)
            hour_float = dt_wib.hour + (dt_wib.minute / 60.0) + (dt_wib.second / 3600.0)
            p = get_realistic_power(hour_float)
            v = round(220.0 + random.uniform(-2.5, 2.5), 1)
            pf = round(random.uniform(0.95, 0.99), 2)
            f = round(50.0 + random.uniform(-0.1, 0.1), 1)
            i = round(p / (v * pf), 3)
            rssi = random.randint(-72, -58)

            delta_e = (p * 10) / 3600000.0
            curr_e += delta_e

            payload = {
                "ts": ts,
                "v": v,
                "i": i,
                "p": p,
                "e": round(curr_e, 3),
                "f": f,
                "pf": pf,
                "rssi": rssi,
                "fw": "1.0.0",
            }
            touched_hours.add((ts // 3600) * 3600)
            touched_sample_timestamps.append(ts)

            process_telemetry_payload(
                session=session,
                device_id="sim-warung",
                payload=payload,
                commit=False,
                update_stats=False,
            )
            inserted_count += 1
            if inserted_count % 30000 == 0:
                elapsed_s = time.time() - t0
                print(f"  Processed {inserted_count}/{total_samples} readings ({elapsed_s:.1f}s)")

        session.commit()
        print(f"  Committed {inserted_count} readings for sim-warung.")

        print(f"  Agregasi {len(touched_hours)} hourly stat buckets untuk sim-warung...")
        for h_start in sorted(touched_hours):
            update_hourly_stat(session, "sim-warung", h_start)
        session.commit()

        # Agregasi hari (WIB)
        days_seen: set[str] = set()
        day_sample_ts: list[int] = []
        for s_ts in touched_sample_timestamps:
            d_str = datetime.fromtimestamp(s_ts, tz=TZ_WIB).strftime("%Y-%m-%d")
            if d_str not in days_seen:
                days_seen.add(d_str)
                day_sample_ts.append(s_ts)

        print(f"  Agregasi {len(day_sample_ts)} daily stat records untuk sim-warung...")
        for s_ts in day_sample_ts:
            update_daily_stat(session, "sim-warung", s_ts)
        session.commit()

        # Update last_seen dan last_data_ts sim-warung
        dev_warung = session.scalar(select(Device).where(Device.id == "sim-warung"))
        if dev_warung:
            dev_warung.last_seen_at = now_ts
            dev_warung.last_data_ts = now_ts - 10
        session.commit()

        # 4. Seeding sim-bench (60 hari hourly_stats murni untuk benchmark)
        print("[4/5] Seeding sim-bench: 60 hari hourly_stats murni (1.440 jam)...")
        bench_hours = 60 * 24
        bench_records = []
        for h_idx in range(bench_hours, 0, -1):
            h_start = now_ts - (h_idx * 3600)
            p_avg = round(random.uniform(320.0, 580.0), 1)
            p_max = round(p_avg + random.uniform(50.0, 200.0), 1)
            p_min = round(max(50.0, p_avg - random.uniform(50.0, 150.0)), 1)
            kwh = round(p_avg / 1000.0, 3)
            samples = 360
            bench_records.append(
                HourlyStat(
                    device_id="sim-bench",
                    hour_start=h_start,
                    kwh=kwh,
                    p_avg=p_avg,
                    p_max=p_max,
                    p_min=p_min,
                    samples=samples,
                )
            )

        session.bulk_save_objects(bench_records)
        dev_bench = session.scalar(select(Device).where(Device.id == "sim-bench"))
        if dev_bench:
            dev_bench.last_seen_at = now_ts
            dev_bench.last_data_ts = now_ts
        session.commit()
        print(f"  Inserted {len(bench_records)} hourly_stats for sim-bench.")

        # 5. Jalankan PRAGMA integrity_check
        print("[5/5] Memeriksa integritas database...")
        res = session.execute(text("PRAGMA integrity_check")).fetchall()
        print(f"  PRAGMA integrity_check: {res}")

        # Summary
        r_cnt = session.scalar(select(text("count(*)")).select_from(Reading))
        h_cnt = session.scalar(select(text("count(*)")).select_from(HourlyStat))
        d_cnt = session.scalar(select(text("count(*)")).select_from(DailyStat))
        print("=" * 60)
        print(f"SEED SUKSES: Readings={r_cnt}, HourlyStats={h_cnt}, DailyStats={d_cnt}")
        print("=" * 60)


if __name__ == "__main__":
    main()
