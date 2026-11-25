import argparse
import json
import logging
import math
import os
import random
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import paho.mqtt.client as mqtt
from sqlalchemy import select
from sqlalchemy.orm import Session

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.models import Device, Reading  # noqa: E402
from app.mqtt_ingest import process_telemetry_payload  # noqa: E402
from app.services.aggregation import update_daily_stat, update_hourly_stat  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] live_demo: %(message)s",
)
logger = logging.getLogger("live_demo_stream")

TZ_WIB = ZoneInfo("Asia/Jakarta")

DEMO_DEVICES = [
    {
        "id": "sim-warung",
        "name": "Warung Kelontong",
        "location": "Warung",
        "mcb_watt": 2200,
        "scale": 1.15,
    },
    {
        "id": "sim-rumah",
        "name": "Panel Utama Rumah",
        "location": "Ruang Tamu",
        "mcb_watt": 2200,
        "scale": 0.85,
    },
]


def realistic_watt_for_hour(hour_wib: float, scale: float = 1.0) -> float:
    """Profil beban listrik rumah/warung Indonesia berbasis gelombang halus 24 jam."""
    morning_peak = math.exp(-((hour_wib - 7.0) ** 2) / 4.5) * 340.0
    midday_activity = math.exp(-((hour_wib - 13.0) ** 2) / 14.0) * 260.0
    evening_peak = math.exp(-((hour_wib - 19.5) ** 2) / 7.5) * 720.0
    base = 160.0 + morning_peak + midday_activity + evening_peak
    jitter = random.uniform(-0.06, 0.08) * base
    return max(90.0, min(1950.0, round((base + jitter) * scale, 1)))


def build_live_sample(
    ts: int,
    prev_p: float,
    curr_e: float,
    interval_sec: int,
    scale: float = 1.0,
) -> tuple[dict[str, Any], float]:
    """Hasilkan 1 payload telemetri valid & akumulasi kWh tanpa lompatan atau reset."""
    dt_wib = datetime.fromtimestamp(ts, tz=TZ_WIB)
    hour_float = dt_wib.hour + dt_wib.minute / 60.0 + dt_wib.second / 3600.0
    target_p = realistic_watt_for_hour(hour_float, scale=scale)

    # Random walk halus agar grafik real-time tampak natural
    step_p = prev_p * 0.72 + target_p * 0.28 + random.uniform(-18.0, 18.0)
    p = max(85.0, min(1950.0, round(step_p, 1)))
    v = round(220.5 + random.uniform(-2.2, 2.2), 1)
    pf = round(random.uniform(0.95, 0.99), 2)
    f = round(50.0 + random.uniform(-0.1, 0.1), 1)
    i = round(p / (v * pf), 3)
    rssi = random.randint(-68, -54)

    next_e = round(curr_e + (p * interval_sec) / 3_600_000.0, 3)
    payload = {
        "ts": int(ts),
        "v": v,
        "i": i,
        "p": p,
        "e": next_e,
        "f": f,
        "pf": pf,
        "rssi": rssi,
        "fw": "1.0.0",
    }
    return payload, next_e


def ensure_demo_devices_and_backfill(
    session: Session,
    *,
    now_ts: int | None = None,
    backfill_hours: int = 24,
    backfill_step_sec: int = 120,
) -> dict[str, tuple[float, float]]:
    """Pastikan unit demo publik ada dan isi histori terbaru bila terjadi kekosongan."""
    now = int(now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp())
    state_by_id: dict[str, tuple[float, float]] = {}

    for spec in DEMO_DEVICES:
        dev_id = spec["id"]
        dev = session.get(Device, dev_id)
        if not dev:
            dev = Device(
                id=dev_id,
                name=spec["name"],
                location=spec["location"],
                mcb_watt=spec["mcb_watt"],
                owner_user_id=None,
                is_public_demo=1,
                status="online",
                last_seen_at=now,
            )
            session.add(dev)
            session.flush()
        else:
            dev.is_public_demo = 1
            if not dev.location:
                dev.location = spec["location"]

        latest_row = session.scalar(
            select(Reading)
            .where(Reading.device_id == dev_id)
            .order_by(Reading.ts.desc())
            .limit(1)
        )

        if latest_row is None or (now - latest_row.ts) > 300:
            start_ts = (
                latest_row.ts + backfill_step_sec
                if latest_row and (now - latest_row.ts) <= backfill_hours * 3600
                else now - backfill_hours * 3600
            )
            curr_e = float(latest_row.e_kwh) if latest_row else 120.0
            prev_p = float(latest_row.p) if latest_row else 360.0 * spec["scale"]
            touched_hours: set[int] = set()
            day_samples: dict[str, int] = {}

            for sample_ts in range(start_ts, now, backfill_step_sec):
                payload, curr_e = build_live_sample(
                    sample_ts,
                    prev_p=prev_p,
                    curr_e=curr_e,
                    interval_sec=backfill_step_sec,
                    scale=spec["scale"],
                )
                prev_p = payload["p"]
                process_telemetry_payload(
                    session=session,
                    device_id=dev_id,
                    payload=payload,
                    commit=False,
                    update_stats=False,
                )
                touched_hours.add((sample_ts // 3600) * 3600)
                day_str = datetime.fromtimestamp(sample_ts, tz=TZ_WIB).strftime("%Y-%m-%d")
                day_samples[day_str] = sample_ts

            session.commit()
            for h_start in sorted(touched_hours):
                update_hourly_stat(session, dev_id, h_start)
            for s_ts in day_samples.values():
                update_daily_stat(session, dev_id, s_ts)
            dev.status = "online"
            dev.last_seen_at = now
            session.commit()
            state_by_id[dev_id] = (prev_p, curr_e)
        else:
            state_by_id[dev_id] = (float(latest_row.p), float(latest_row.e_kwh))

    return state_by_id


def run_stream(interval_sec: int = 10, backfill_hours: int = 24) -> None:
    cfg = get_settings()
    init_db()

    with SessionLocal() as session:
        dev_states = ensure_demo_devices_and_backfill(
            session,
            backfill_hours=backfill_hours,
        )
    logger.info("Siap menyiarkan demo real-time untuk %s", list(dev_states.keys()))

    running = True

    def _stop_handler(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _stop_handler)
    signal.signal(signal.SIGINT, _stop_handler)

    clients: dict[str, mqtt.Client] = {}
    for spec in DEMO_DEVICES:
        dev_id = spec["id"]
        c = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"voltku_demo_{dev_id}",
        )
        if cfg.mqtt_user and cfg.mqtt_pass:
            c.username_pw_set(cfg.mqtt_user, cfg.mqtt_pass)
        elif cfg.mqtt_user:
            c.username_pw_set(cfg.mqtt_user, "")

        status_topic = f"energy/{dev_id}/status"
        c.will_set(status_topic, payload="offline", qos=1, retain=True)
        c.connect(cfg.mqtt_host, cfg.mqtt_port, 60)
        c.loop_start()
        c.publish(status_topic, payload="online", qos=1, retain=True)
        clients[dev_id] = c

    try:
        while running:
            now_ts = int(datetime.now(timezone.utc).timestamp())
            for spec in DEMO_DEVICES:
                dev_id = spec["id"]
                prev_p, curr_e = dev_states[dev_id]
                payload, next_e = build_live_sample(
                    now_ts,
                    prev_p=prev_p,
                    curr_e=curr_e,
                    interval_sec=interval_sec,
                    scale=spec["scale"],
                )
                dev_states[dev_id] = (payload["p"], next_e)
                clients[dev_id].publish(
                    f"energy/{dev_id}/telemetry",
                    json.dumps(payload),
                    qos=1,
                )
                clients[dev_id].publish(
                    f"energy/{dev_id}/status",
                    payload="online",
                    qos=1,
                    retain=True,
                )

            # Tidur bertahap agar cepat merespons SIGTERM
            for _ in range(interval_sec):
                if not running:
                    break
                time.sleep(1)
    finally:
        for dev_id, c in clients.items():
            try:
                c.publish(f"energy/{dev_id}/status", payload="offline", qos=1, retain=True)
                time.sleep(0.2)
                c.loop_stop()
                c.disconnect()
            except Exception:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Streamer telemetri demo real-time VoltKu")
    parser.add_argument("--interval", type=int, default=10, help="Interval publish detik")
    parser.add_argument(
        "--backfill-hours",
        type=int,
        default=24,
        help="Backfill histori jam ke belakang jika data kosong/terputus",
    )
    args = parser.parse_args()
    run_stream(interval_sec=args.interval, backfill_hours=args.backfill_hours)


if __name__ == "__main__":
    main()

