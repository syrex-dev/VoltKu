import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# Tambahkan direktori root dan backend ke path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

# Load .env dari root
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "energy_backend")
MQTT_PASS = os.getenv("MQTT_PASS", "")

TZ_WIB = ZoneInfo("Asia/Jakarta")


def get_realistic_power(hour_wib: float) -> float:
    """Menghasilkan profil daya realistis rumah tangga Indonesia (W) berdasarkan jam WIB."""
    if 0.0 <= hour_wib < 5.0:
        # Malam / tidur: base standby, kulkas (120 - 160 W)
        p = 140.0 + random.uniform(-15.0, 20.0)
    elif 5.0 <= hour_wib < 8.0:
        # Pagi: persiapan, pompa air, dispenser, rice cooker (400 - 700 W)
        p = 450.0 + random.uniform(-40.0, 180.0)
    elif 8.0 <= hour_wib < 17.0:
        # Siang: aktivitas harian, kulkas, AC sesekali, laptop (250 - 450 W)
        p = 350.0 + random.uniform(-30.0, 80.0)
    elif 17.0 <= hour_wib < 22.0:
        # Puncak malam: lampu, TV, masak, AC (700 - 1100 W)
        p = 850.0 + random.uniform(-60.0, 220.0)
    else:
        # 22.0 - 24.0: istirahat, lampu mati, AC kamar (250 - 380 W)
        p = 290.0 + random.uniform(-20.0, 60.0)

    return max(80.0, min(1800.0, round(p, 1)))


def create_payload(
    ts: int,
    v: float = 220.0,
    i: float = 1.2,
    p: float = 264.0,
    e: float = 10.0,
    f: float = 50.0,
    pf: float = 0.98,
    rssi: int = -60,
    fw: str = "1.0.0",
) -> dict[str, Any]:
    return {
        "ts": ts,
        "v": round(v, 1),
        "i": round(i, 3),
        "p": round(p, 1),
        "e": round(e, 3),
        "f": round(f, 1),
        "pf": round(pf, 2),
        "rssi": rssi,
        "fw": fw,
    }


def publish_message(client: mqtt.Client, topic: str, payload: dict[str, Any]) -> None:
    msg_str = json.dumps(payload)
    client.publish(topic, msg_str, qos=1)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Published to {topic}: {msg_str}")


def run_simulator() -> None:
    parser = argparse.ArgumentParser(description="Simulator Telemetry PZEM-004T / ESP32")
    parser.add_argument(
        "--mode",
        choices=[
            "normal",
            "buffer",
            "reset",
            "invalid",
            "duplicate",
            "out-of-order",
            "overload",
            "lowvolt",
        ],
        default="normal",
        help="Skenario simulasi telemetry",
    )
    parser.add_argument("--device", default="sim-warung", help="Device ID")
    parser.add_argument("--interval", type=int, default=10, help="Interval pengiriman (detik)")
    parser.add_argument("--count", type=int, default=10, help="Jumlah sampel")
    parser.add_argument(
        "--backfill-days", type=int, default=0, help="Isi data historis N hari ke belakang"
    )
    parser.add_argument(
        "--seed-db",
        action="store_true",
        help="Seed langsung ke database lokal menggunakan fungsi ingest backend",
    )
    parser.add_argument(
        "--overload-seconds",
        type=int,
        default=120,
        help="Durasi fase overload dalam detik (default 120)",
    )
    parser.add_argument(
        "--lowvolt-seconds",
        type=int,
        default=60,
        help="Durasi fase tegangan rendah dalam detik (default 60)",
    )
    args = parser.parse_args()

    # Mode Backfill: Isi data historis N hari ke belakang
    if args.backfill_days > 0:
        now = int(datetime.now(timezone.utc).timestamp())
        now = (now // args.interval) * args.interval
        start_ts = now - (args.backfill_days * 86400)
        total_samples = (now - start_ts) // args.interval
        print(f"Generating {total_samples} historical samples for {args.backfill_days} days...")
        dt_start_wib = datetime.fromtimestamp(start_ts, tz=TZ_WIB).strftime("%Y-%m-%d %H:%M:%S")
        dt_now_wib = datetime.fromtimestamp(now, tz=TZ_WIB).strftime("%Y-%m-%d %H:%M:%S")
        print(f"Range UTC: {start_ts} ({dt_start_wib} WIB) s.d. {now} ({dt_now_wib} WIB)")

        if args.seed_db:
            print("Running in DIRECT DB SEED mode (--seed-db)...")
            from app.db import SessionLocal, init_db
            from app.mqtt_ingest import process_telemetry_payload
            from app.services.aggregation import update_daily_stat, update_hourly_stat

            init_db()
            session = SessionLocal()

            curr_e = 100.0
            touched_hours: set[int] = set()
            touched_sample_timestamps: list[int] = []

            t0 = time.time()
            inserted_count = 0

            for ts in range(start_ts, now, args.interval):
                dt_wib = datetime.fromtimestamp(ts, tz=TZ_WIB)
                hour_float = dt_wib.hour + (dt_wib.minute / 60.0) + (dt_wib.second / 3600.0)

                p = get_realistic_power(hour_float)
                v = round(220.0 + random.uniform(-2.5, 2.5), 1)
                pf = round(random.uniform(0.95, 0.99), 2)
                f = round(50.0 + random.uniform(-0.1, 0.1), 1)
                i = round(p / (v * pf), 3)
                rssi = random.randint(-72, -58)

                # delta Wh = P * dt_detik / 3600. e_kwh += delta Wh / 1000
                delta_e = (p * args.interval) / 3600000.0
                curr_e += delta_e

                payload = create_payload(
                    ts=ts, v=v, i=i, p=p, e=round(curr_e, 3), f=f, pf=pf, rssi=rssi
                )

                hour_start = (ts // 3600) * 3600
                touched_hours.add(hour_start)
                touched_sample_timestamps.append(ts)

                process_telemetry_payload(
                    session=session,
                    device_id=args.device,
                    payload=payload,
                    commit=False,
                    update_stats=False,
                )
                inserted_count += 1
                if inserted_count % 20000 == 0:
                    elapsed = time.time() - t0
                    print(f"  Processed {inserted_count}/{total_samples} in {elapsed:.1f}s")

            # Commit seluruh pembacaan dalam satu transaksi tunggal
            session.commit()
            print(
                f"Inserted all {inserted_count} readings in single transaction. Computing stats..."
            )

            # Agregasi jam
            print(f"Calculating {len(touched_hours)} hourly stat buckets...")
            for h_start in sorted(touched_hours):
                update_hourly_stat(session, args.device, h_start)
            session.commit()

            # Agregasi hari (berdasarkan WIB)
            # Kumpulkan sampel representatif untuk setiap tanggal unik WIB
            days_seen: set[str] = set()
            day_sample_ts: list[int] = []
            for s_ts in touched_sample_timestamps:
                d_str = datetime.fromtimestamp(s_ts, tz=TZ_WIB).strftime("%Y-%m-%d")
                if d_str not in days_seen:
                    days_seen.add(d_str)
                    day_sample_ts.append(s_ts)

            print(f"Calculating {len(day_sample_ts)} daily stat records...")
            for s_ts in day_sample_ts:
                update_daily_stat(session, args.device, s_ts)
            session.commit()

            session.close()
            total_time = time.time() - t0
            print(f"DB Seed completed successfully in {total_time:.2f} seconds!")
            return

        else:
            # Lewat MQTT Broker dengan pembatasan laju agar antrean tidak penuh
            client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"sim_{args.device}",
            )
            if MQTT_USER and MQTT_PASS:
                client.username_pw_set(MQTT_USER, MQTT_PASS)

            print(f"Connecting to MQTT broker at {MQTT_HOST}:{MQTT_PORT}...")
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            client.loop_start()
            time.sleep(1)

            topic = f"energy/{args.device}/telemetry"
            curr_e = 100.0

            sent_count = 0
            for ts in range(start_ts, now, args.interval):
                dt_wib = datetime.fromtimestamp(ts, tz=TZ_WIB)
                hour_float = dt_wib.hour + (dt_wib.minute / 60.0) + (dt_wib.second / 3600.0)

                p = get_realistic_power(hour_float)
                v = round(220.0 + random.uniform(-2.5, 2.5), 1)
                pf = round(random.uniform(0.95, 0.99), 2)
                f = round(50.0 + random.uniform(-0.1, 0.1), 1)
                i = round(p / (v * pf), 3)
                rssi = random.randint(-72, -58)

                delta_e = (p * args.interval) / 3600000.0
                curr_e += delta_e

                payload = create_payload(
                    ts=ts, v=v, i=i, p=p, e=round(curr_e, 3), f=f, pf=pf, rssi=rssi
                )
                client.publish(topic, json.dumps(payload), qos=1)
                sent_count += 1

                # Pembatasan laju agar antrean IngestService (kapasitas 1000) tidak overload
                time.sleep(0.005)

                if sent_count % 1000 == 0:
                    print(f"  Published {sent_count}/{total_samples} samples via MQTT...")

            print("MQTT Backfill complete!")
            time.sleep(2)
            client.loop_stop()
            client.disconnect()
            return

    # Skenario Berjalan Real-time / Pengujian Spesifik
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"sim_{args.device}",
    )
    if MQTT_USER and MQTT_PASS:
        client.username_pw_set(MQTT_USER, MQTT_PASS)

    print(f"Connecting to MQTT broker at {MQTT_HOST}:{MQTT_PORT}...")
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()
    time.sleep(1)

    topic = f"energy/{args.device}/telemetry"
    curr_ts = int(datetime.now(timezone.utc).timestamp())
    curr_e = 50.0

    if args.mode == "normal":
        print("Starting NORMAL scenario (every 10s)...")
        for _ in range(args.count):
            p = 260.0 + random.uniform(-10, 10)
            v = 220.0 + random.uniform(-2, 2)
            i = p / v
            curr_e += (p * args.interval) / (3600.0 * 1000.0)
            payload = create_payload(ts=curr_ts, v=v, i=i, p=p, e=curr_e)
            publish_message(client, topic, payload)
            curr_ts += args.interval
            time.sleep(args.interval)

    elif args.mode == "buffer":
        print("Starting BUFFER / REPLAY scenario: collecting samples offline, then flushing...")
        buffered = []
        for _ in range(args.count):
            p = 300.0 + random.uniform(-5, 5)
            v = 220.0
            i = p / v
            curr_e += (p * args.interval) / (3600.0 * 1000.0)
            buffered.append(create_payload(ts=curr_ts, v=v, i=i, p=p, e=curr_e))
            curr_ts += args.interval

        print(f"Flushing {len(buffered)} buffered samples in burst...")
        for p in buffered:
            publish_message(client, topic, p)
            time.sleep(0.1)

    elif args.mode == "reset":
        print("Starting COUNTER RESET scenario...")
        publish_message(client, topic, create_payload(ts=curr_ts, e=50.0))
        curr_ts += args.interval
        time.sleep(1)
        print("Counter reset to 0.005 kWh!")
        publish_message(client, topic, create_payload(ts=curr_ts, e=0.005))

    elif args.mode == "invalid":
        print("Starting INVALID data scenario (BE-02 out of range)...")
        publish_message(client, topic, create_payload(ts=curr_ts, v=450.0, p=30000.0, i=-5.0))

    elif args.mode == "duplicate":
        print("Starting DUPLICATE scenario...")
        payload = create_payload(ts=curr_ts, e=curr_e)
        publish_message(client, topic, payload)
        time.sleep(1)
        print("Sending duplicate with same ts...")
        publish_message(client, topic, payload)

    elif args.mode == "out-of-order":
        print("Starting OUT-OF-ORDER scenario...")
        ts1 = curr_ts
        ts2 = curr_ts + args.interval
        ts3 = curr_ts + (2 * args.interval)

        publish_message(client, topic, create_payload(ts=ts1, e=50.0))
        time.sleep(1)
        publish_message(client, topic, create_payload(ts=ts3, e=50.004))
        time.sleep(1)
        print("Sending middle ts out of order...")
        publish_message(client, topic, create_payload(ts=ts2, e=50.002))

    elif args.mode == "overload":
        overload_samples = max(1, (args.overload_seconds // args.interval) + 1)
        print(
            f"Starting OVERLOAD scenario for {args.device} "
            f"(P > 2200 W for {args.overload_seconds}s, {overload_samples} samples, then recovery)..."
        )
        # Fase 1: Overload selama overload_seconds
        for i in range(overload_samples):
            p = 2640.0 + random.uniform(-20, 20)
            v = 220.0 + random.uniform(-1, 1)
            i_val = p / v
            curr_e += (p * args.interval) / (3600.0 * 1000.0)
            payload = create_payload(ts=curr_ts, v=v, i=i_val, p=p, e=curr_e)
            print(f"  [Overload {i+1}/{overload_samples}] P = {p:.1f} W")
            publish_message(client, topic, payload)
            curr_ts += args.interval
            time.sleep(args.interval)

        # Fase 2: Normal / Recovery selama 70 detik (8 sampel @ 10s)
        print(f"Starting RECOVERY phase for {args.device} (P < 2090 W)...")
        recovery_samples = 8
        for i in range(recovery_samples):
            p = 350.0 + random.uniform(-10, 10)
            v = 220.0 + random.uniform(-1, 1)
            i_val = p / v
            curr_e += (p * args.interval) / (3600.0 * 1000.0)
            payload = create_payload(ts=curr_ts, v=v, i=i_val, p=p, e=curr_e)
            print(f"  [Recovery {i+1}/{recovery_samples}] P = {p:.1f} W")
            publish_message(client, topic, payload)
            curr_ts += args.interval
            time.sleep(args.interval)

    elif args.mode == "lowvolt":
        low_samples = max(1, (args.lowvolt_seconds // args.interval) + 1)
        print(
            f"Starting LOW VOLTAGE scenario for {args.device} "
            f"(V < 200 V for {args.lowvolt_seconds}s, {low_samples} samples, then recovery)..."
        )
        # Fase 1: Tegangan rendah
        for i in range(low_samples):
            v = 192.0 + random.uniform(-2, 2)
            p = 380.0
            i_val = p / v
            curr_e += (p * args.interval) / (3600.0 * 1000.0)
            payload = create_payload(ts=curr_ts, v=v, i=i_val, p=p, e=curr_e)
            print(f"  [Low Volt {i+1}/{low_samples}] V = {v:.1f} V")
            publish_message(client, topic, payload)
            curr_ts += args.interval
            time.sleep(args.interval)

        # Fase 2: Tegangan normal (4 sampel @ 10s)
        print(f"Starting NORMAL VOLTAGE recovery for {args.device} (V in 205-235 V)...")
        for i in range(low_samples):
            v = 220.0 + random.uniform(-2, 2)
            p = 380.0
            i_val = p / v
            curr_e += (p * args.interval) / (3600.0 * 1000.0)
            payload = create_payload(ts=curr_ts, v=v, i=i_val, p=p, e=curr_e)
            print(f"  [Volt Recovery {i+1}/{low_samples}] V = {v:.1f} V")
            publish_message(client, topic, payload)
            curr_ts += args.interval
            time.sleep(args.interval)

    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    run_simulator()
