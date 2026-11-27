import json
import logging
import queue
import threading
from datetime import datetime, timezone
from typing import Any, Optional

import paho.mqtt.client as mqtt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.constants import OFFLINE_THRESHOLD_SECONDS
from app.db import SessionLocal
from app.models import Device, Reading
from app.services.aggregation import update_daily_stat, update_hourly_stat
from app.services.delta import calculate_delta_kwh
from app.services.retention import get_retention_cutoff_ts

logger = logging.getLogger(__name__)

# Minimum epoch: 2025-01-01 00:00:00 UTC
MIN_VALID_TS = 1735689600
# Toleransi masa depan: 5 menit (300 detik)
FUTURE_TOLERANCE_SECONDS = 300


def get_device_status(
    device: Device,
    now_utc: Optional[int] = None,
    threshold_seconds: int = OFFLINE_THRESHOLD_SECONDS,
) -> str:
    """Mengembalikan status online/offline berdasarkan LWT dan batas threshold last_seen_at."""
    if now_utc is None:
        now_utc = int(datetime.now(timezone.utc).timestamp())
    if device.status == "offline":
        return "offline"
    if not device.last_seen_at or (now_utc - device.last_seen_at) > threshold_seconds:
        return "offline"
    return "online"


def validate_telemetry_payload(
    data: dict[str, Any],
    check_retention: bool = False,
    now_utc: Optional[int] = None,
) -> tuple[bool, Optional[str]]:
    """Memvalidasi payload telemetry sesuai kontrak dan aturan BE-02."""
    required_keys = ("ts", "v", "i", "p", "e", "f", "pf")
    for k in required_keys:
        if k not in data:
            return False, f"Missing required key '{k}'"

    try:
        ts = int(data["ts"])
        v = float(data["v"])
        i = float(data["i"])
        p = float(data["p"])
        e = float(data["e"])
        _ = float(data["f"])
        _ = float(data["pf"])
    except (ValueError, TypeError) as err:
        return False, f"Invalid value type: {err}"

    # Validasi rentang BE-02
    if not (0.0 <= v <= 300.0):
        return False, f"Voltage {v} V out of range (0-300 V)"
    if not (0.0 <= i <= 100.0):
        return False, f"Current {i} A out of range (0-100 A)"
    if not (0.0 <= p <= 25000.0):
        return False, f"Power {p} W out of range (0-25000 W)"
    if e < 0.0:
        return False, f"Energy {e} kWh cannot be negative"

    # Validasi timestamp
    if now_utc is None:
        now_utc = int(datetime.now(timezone.utc).timestamp())
    if ts < MIN_VALID_TS:
        return False, f"Timestamp {ts} before 2025-01-01"
    if ts > (now_utc + FUTURE_TOLERANCE_SECONDS):
        return False, f"Timestamp {ts} more than 5 minutes in future (now={now_utc})"

    # Validasi retensi: tolak data yang lebih tua dari batas retensi (hari penuh > 14 hari)
    if check_retention:
        cutoff_ts = get_retention_cutoff_ts(now_utc)
        if ts < cutoff_ts:
            return False, f"Timestamp {ts} older than 14-day retention cutoff ({cutoff_ts})"

    return True, None


def process_telemetry_payload(
    session: Session,
    device_id: str,
    payload: dict[str, Any],
    default_mcb_watt: int = 2200,
    commit: bool = True,
    update_stats: bool = True,
    check_retention: bool = False,
    now_utc: Optional[int] = None,
) -> Optional[Reading]:
    """Memproses payload telemetry secara deterministik (dapat dipanggil langsung tanpa broker)."""
    is_valid, err_msg = validate_telemetry_payload(
        payload, check_retention=check_retention, now_utc=now_utc
    )
    if not is_valid:
        logger.warning("Rejected telemetry from %s: %s", device_id, err_msg)
        return None

    ts = int(payload["ts"])

    # 1. Cek duplikasi (device_id + ts) -> Idempoten
    existing = session.scalar(
        select(Reading).where(Reading.device_id == device_id, Reading.ts == ts)
    )
    if existing:
        logger.debug("Duplicate reading ignored for device %s at ts %s", device_id, ts)
        return existing

    # 2. Registrasi otomatis device jika belum terdaftar, atau update last_seen_at & last_data_ts
    now_server = int(datetime.now(timezone.utc).timestamp())
    device = session.scalar(select(Device).where(Device.id == device_id))
    if not device:
        device = Device(
            id=device_id,
            name=device_id,
            mcb_watt=default_mcb_watt,
            created_at=now_server,
            last_seen_at=now_server,
            last_data_ts=ts,
            status="online",
        )
        session.add(device)
        session.flush()
    else:
        # Replay data lama tidak memundurkan last_seen_at maupun last_data_ts
        device.last_seen_at = max(device.last_seen_at or 0, now_server)
        device.last_data_ts = max(device.last_data_ts or 0, ts)
        device.status = "online"
        session.flush()

    mcb_watt = device.mcb_watt

    # 3. Hitung delta_kwh dan flag is_gap
    e_kwh = float(payload["e"])
    delta_kwh, is_gap, _ = calculate_delta_kwh(
        session=session,
        device_id=device_id,
        ts=ts,
        e_kwh=e_kwh,
        mcb_watt=mcb_watt,
    )

    reading = Reading(
        device_id=device_id,
        ts=ts,
        v=float(payload["v"]),
        i=float(payload["i"]),
        p=float(payload["p"]),
        e_kwh=e_kwh,
        delta_kwh=delta_kwh,
        f=float(payload["f"]),
        pf=float(payload["pf"]),
        rssi=int(payload.get("rssi", 0)),
        is_gap=is_gap,
    )
    session.add(reading)
    session.flush()

    # 4. Rekonsiliasi out-of-order (jika ada sampel sesudahnya yang perlu dihitung ulang)
    next_reading = session.scalar(
        select(Reading)
        .where(Reading.device_id == device_id, Reading.ts > ts)
        .order_by(Reading.ts.asc())
        .limit(1)
    )
    if next_reading:
        # Hitung ulang delta untuk reading sesudahnya terhadap reading baru ini
        new_next_delta, next_gap, _ = calculate_delta_kwh(
            session=session,
            device_id=device_id,
            ts=next_reading.ts,
            e_kwh=next_reading.e_kwh,
            mcb_watt=mcb_watt,
        )
        next_reading.delta_kwh = new_next_delta
        next_reading.is_gap = next_gap
        session.flush()

        # Update agregat untuk next_reading
        update_hourly_stat(session, device_id, next_reading.ts)
        update_daily_stat(session, device_id, next_reading.ts)

    # 5. Update agregat jam dan hari untuk reading saat ini
    if update_stats:
        update_hourly_stat(session, device_id, ts)
        update_daily_stat(session, device_id, ts)

    if commit:
        session.commit()
    return reading


class IngestService:
    def __init__(self, max_queue_size: int = 1000) -> None:
        self.queue: queue.Queue[tuple[str, str]] = queue.Queue(maxsize=max_queue_size)
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._mqtt_client: Optional[mqtt.Client] = None

    def start_worker(self) -> None:
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        logger.info("MQTT Ingest worker thread started.")

    def stop_worker(self) -> None:
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=3)
        logger.info("MQTT Ingest worker thread stopped.")

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                topic, payload_str = self.queue.get(timeout=0.5)
            except queue.Empty:
                continue

            try:
                self._handle_message(topic, payload_str)
            except Exception as e:
                logger.error("Error processing message from topic %s: %s", topic, e, exc_info=True)
            finally:
                self.queue.task_done()

    def _handle_message(self, topic: str, payload_str: str) -> None:
        parts = topic.split("/")
        if len(parts) < 3 or parts[0] != "energy":
            return

        device_id = parts[1]
        action = parts[2]

        if action == "telemetry":
            try:
                data = json.loads(payload_str)
            except json.JSONDecodeError:
                logger.warning("Invalid JSON from %s: %s", topic, payload_str[:100])
                return

            settings = get_settings()
            with SessionLocal() as session:
                process_telemetry_payload(
                    session=session,
                    device_id=device_id,
                    payload=data,
                    default_mcb_watt=settings.default_mcb_watt,
                    check_retention=True,
                )
        elif action == "status":
            clean_status = payload_str.strip().lower()
            if clean_status in ("online", "offline"):
                settings = get_settings()
                now_utc = int(datetime.now(timezone.utc).timestamp())
                with SessionLocal() as session:
                    device = session.scalar(select(Device).where(Device.id == device_id))
                    if not device:
                        device = Device(
                            id=device_id,
                            name=device_id,
                            mcb_watt=settings.default_mcb_watt,
                            created_at=now_utc,
                            last_seen_at=now_utc if clean_status == "online" else None,
                            last_data_ts=None,
                            status=clean_status,
                        )
                        session.add(device)
                    else:
                        device.status = clean_status
                        if clean_status == "online":
                            device.last_seen_at = max(device.last_seen_at or 0, now_utc)
                    session.commit()
            logger.info("Status message from device %s: %s", device_id, payload_str)

    def enqueue_message(self, topic: str, payload_str: str) -> bool:
        try:
            self.queue.put_nowait((topic, payload_str))
            return True
        except queue.Full:
            logger.warning("Ingest queue is full! Dropping message from %s.", topic)
            return False

    def init_mqtt_client(self) -> mqtt.Client:
        settings = get_settings()
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="energy_backend",
            clean_session=False,
        )
        if settings.mqtt_user and settings.mqtt_pass:
            client.username_pw_set(settings.mqtt_user, settings.mqtt_pass)
        if settings.mqtt_use_tls:
            ca_path = (settings.mqtt_ca_cert or "").strip() or None
            client.tls_set(ca_certs=ca_path)
            if settings.mqtt_tls_insecure:
                client.tls_insecure_set(True)

        def on_connect(
            c: mqtt.Client, userdata: Any, flags: Any, rc: Any, properties: Any = None
        ) -> None:
            if rc == 0:
                logger.info("Connected to Mosquitto broker.")
                c.subscribe("energy/+/telemetry", qos=1)
                c.subscribe("energy/+/status", qos=1)
            else:
                logger.error("Failed to connect to Mosquitto: rc=%s", rc)

        def on_message(c: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
            topic = msg.topic
            payload_str = msg.payload.decode("utf-8", errors="ignore")
            self.enqueue_message(topic, payload_str)

        client.on_connect = on_connect
        client.on_message = on_message
        client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._mqtt_client = client
        return client

    def start_mqtt(self) -> None:
        settings = get_settings()
        if not self._mqtt_client:
            self.init_mqtt_client()
        assert self._mqtt_client is not None
        try:
            # Gunakan connect_async + loop_start agar tahan startup race dengan Mosquitto
            self._mqtt_client.connect_async(settings.mqtt_host, settings.mqtt_port, 60)
            self._mqtt_client.loop_start()
            logger.info(
                "MQTT async loop started (target %s:%s).",
                settings.mqtt_host,
                settings.mqtt_port,
            )
        except Exception as err:
            logger.warning(
                "Could not start MQTT loop (%s:%s): %s",
                settings.mqtt_host,
                settings.mqtt_port,
                err,
            )

    def stop_mqtt(self) -> None:
        if self._mqtt_client:
            try:
                self._mqtt_client.loop_stop()
                self._mqtt_client.disconnect()
            except Exception:
                pass


ingest_service = IngestService()
