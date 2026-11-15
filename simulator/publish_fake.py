import argparse
import json
import os
import random
import time
from datetime import datetime, timezone
from typing import Any

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# Load .env dari root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "energy_backend")
MQTT_PASS = os.getenv("MQTT_PASS", "")


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
        choices=["normal", "buffer", "reset", "invalid", "duplicate", "out-of-order"],
        default="normal",
        help="Skenario simulasi telemetry",
    )
    parser.add_argument("--device", default="esp32_device_1", help="Device ID")
    parser.add_argument("--interval", type=int, default=10, help="Interval pengiriman (detik)")
    parser.add_argument("--count", type=int, default=10, help="Jumlah sampel")
    parser.add_argument(
        "--backfill-days", type=int, default=0, help="Isi data historis N hari ke belakang"
    )
    args = parser.parse_args()

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

    # Mode Backfill: Isi data historis N hari ke belakang secara cepat
    if args.backfill_days > 0:
        print(f"Running backfill for {args.backfill_days} days...")
        now = int(datetime.now(timezone.utc).timestamp())
        start_ts = now - (args.backfill_days * 86400)
        curr_e = 100.0

        for ts in range(start_ts, now, args.interval):
            # Simulasi profil daya realistis (200W - 1200W)
            hour_wib = (datetime.fromtimestamp(ts, tz=timezone.utc).hour + 7) % 24
            base_p = 150.0 if (0 <= hour_wib < 5) else 500.0
            p = base_p + random.uniform(0, 300)
            v = 220.0 + random.uniform(-5, 5)
            i = p / v
            delta_e = (p * args.interval) / (3600.0 * 1000.0)
            curr_e += delta_e

            payload = create_payload(ts=ts, v=v, i=i, p=p, e=curr_e)
            client.publish(topic, json.dumps(payload), qos=1)

        print("Backfill complete!")
        client.loop_stop()
        client.disconnect()
        return

    # Skenario Berjalan
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
        # Sampel 1 normal
        publish_message(client, topic, create_payload(ts=curr_ts, e=50.0))
        curr_ts += args.interval
        time.sleep(1)
        # Sampel 2 counter direset ke 0.005 kWh
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

        # Kirim ts1 dan ts3 dulu, baru ts2
        publish_message(client, topic, create_payload(ts=ts1, e=50.0))
        time.sleep(1)
        publish_message(client, topic, create_payload(ts=ts3, e=50.004))
        time.sleep(1)
        print("Sending middle ts out of order...")
        publish_message(client, topic, create_payload(ts=ts2, e=50.002))

    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    run_simulator()
