import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import AlertState, Anomaly, Device, Reading, Setting
from app.mqtt_ingest import get_device_status
from app.services.notifier import send_alert_notification

logger = logging.getLogger(__name__)
TZ_WIB = ZoneInfo("Asia/Jakarta")

STARTUP_GRACE_PERIOD_SECONDS = 120
MIN_SAMPLES_POWER = 3  # Minimal 3 sampel dalam jendela 60 detik
MIN_SAMPLES_VOLTAGE = 2  # Minimal 2 sampel dalam jendela 30 detik

_module_startup_time = int(time.time())


def get_startup_time() -> int:
    return _module_startup_time


def set_startup_time(ts: int) -> None:
    global _module_startup_time
    _module_startup_time = ts


def _get_setting_int(session: Session, key: str, default: int) -> int:
    val = session.scalar(select(Setting.value).where(Setting.key == key))
    if val is not None:
        try:
            return int(val)
        except ValueError:
            pass
    return default


def _format_time_wib(epoch_ts: int) -> str:
    dt = datetime.fromtimestamp(epoch_ts, tz=TZ_WIB)
    return dt.strftime("%H.%M")


def evaluate_device_alerts(
    session: Session,
    device: Device,
    now_ts: int,
    power_limit_w: int,
    alert_cooldown_min: int,
) -> list[str]:
    """Mengevaluasi kondisi alert L1 untuk satu perangkat:

    - offline (last_seen_at > 120s)
    - power_limit (semua sampel jendela 60s > power_limit_w)
    - voltage_low (semua sampel jendela 30s < 200V)
    - voltage_high (semua sampel jendela 30s > 240V)
    """
    settings = get_settings()
    cooldown_seconds = alert_cooldown_min * 60
    sent_messages: list[str] = []

    # Ambil status alert saat ini untuk perangkat ini
    existing_states = {
        state.alert_type: state
        for state in session.scalars(
            select(AlertState).where(AlertState.device_id == device.id)
        ).all()
    }

    # ---------------------------------------------------------
    # 1. EVALUASI STATUS OFFLINE
    # ---------------------------------------------------------
    is_offline = get_device_status(device, now_utc=now_ts) == "offline"
    offline_state = existing_states.get("offline")

    if is_offline:
        if not offline_state or offline_state.state != "active":
            # Alert baru
            msg = f"[PERINGATAN] {device.name} - Perangkat offline (tidak ada data > 120 detik)"
            if send_alert_notification(msg):
                sent_messages.append(msg)
                if not offline_state:
                    offline_state = AlertState(
                        device_id=device.id,
                        alert_type="offline",
                        state="active",
                        since=now_ts,
                        last_notified_at=now_ts,
                        details_json=json.dumps({"last_seen_at": device.last_seen_at}),
                    )
                    session.add(offline_state)
                else:
                    offline_state.state = "active"
                    offline_state.since = now_ts
                    offline_state.last_notified_at = now_ts
                    offline_state.details_json = json.dumps(
                        {"last_seen_at": device.last_seen_at}
                    )

                session.add(
                    Anomaly(
                        device_id=device.id,
                        ts=now_ts,
                        type="offline",
                        severity="warning",
                        details_json=json.dumps({"last_seen_at": device.last_seen_at}),
                        message=msg,
                        notified=1,
                    )
                )
                session.commit()
        elif (now_ts - offline_state.last_notified_at) >= cooldown_seconds:
            # Pengingat setelah cooldown
            msg = (
                f"[PENGINGAT] {device.name} - Perangkat masih offline "
                f"sejak {_format_time_wib(offline_state.since)} WIB"
            )
            if send_alert_notification(msg):
                sent_messages.append(msg)
                offline_state.last_notified_at = now_ts
                session.add(
                    Anomaly(
                        device_id=device.id,
                        ts=now_ts,
                        type="offline_reminder",
                        severity="warning",
                        details_json=json.dumps({"since": offline_state.since}),
                        message=msg,
                        notified=1,
                    )
                )
                session.commit()
    else:
        # Perangkat online: kirim pesan pulih HANYA jika alert offline pernah terkirim
        if offline_state and offline_state.state == "active":
            msg = f"[PULIH] {device.name} - Perangkat online kembali"
            if send_alert_notification(msg):
                sent_messages.append(msg)
                offline_state.state = "cleared"
                offline_state.last_notified_at = now_ts
                offline_state.details_json = None
                session.add(
                    Anomaly(
                        device_id=device.id,
                        ts=now_ts,
                        type="offline_resolved",
                        severity="info",
                        details_json=json.dumps({"online_at": now_ts}),
                        message=msg,
                        notified=1,
                    )
                )
                session.commit()

    # ---------------------------------------------------------
    # 2. EVALUASI DAYA & TEGANGAN DARI JENDELA READINGS
    # ---------------------------------------------------------
    # Ambil sampel pembacaan dalam jendela 60 detik
    readings_60s = session.scalars(
        select(Reading)
        .where(Reading.device_id == device.id, Reading.ts >= now_ts - 60)
        .order_by(Reading.ts.asc())
    ).all()

    # Readings 30 detik untuk tegangan
    readings_30s = [r for r in readings_60s if r.ts >= now_ts - 30]

    # --- A. DAYA LISTRIK (POWER LIMIT) ---
    power_state = existing_states.get("power_limit")
    if len(readings_60s) >= MIN_SAMPLES_POWER:
        all_above_limit = all(r.p > power_limit_w for r in readings_60s)
        all_recovered = all(r.p < (0.95 * power_limit_w) for r in readings_60s)

        if all_above_limit:
            avg_p = round(sum(r.p for r in readings_60s) / len(readings_60s), 1)
            if not power_state or power_state.state != "active":
                msg = (
                    f"[PERINGATAN] {device.name} - Daya melebihi batas wajar: "
                    f"{avg_p} W > {power_limit_w} W"
                )
                if send_alert_notification(msg):
                    sent_messages.append(msg)
                    details = {
                        "avg_p": avg_p,
                        "limit_w": power_limit_w,
                        "samples": len(readings_60s),
                    }
                    if not power_state:
                        power_state = AlertState(
                            device_id=device.id,
                            alert_type="power_limit",
                            state="active",
                            since=now_ts,
                            last_notified_at=now_ts,
                            details_json=json.dumps(details),
                        )
                        session.add(power_state)
                    else:
                        power_state.state = "active"
                        power_state.since = now_ts
                        power_state.last_notified_at = now_ts
                        power_state.details_json = json.dumps(details)

                    session.add(
                        Anomaly(
                            device_id=device.id,
                            ts=now_ts,
                            type="power_limit",
                            severity="warning",
                            details_json=json.dumps(details),
                            message=msg,
                            notified=1,
                        )
                    )
                    session.commit()
            elif (now_ts - power_state.last_notified_at) >= cooldown_seconds:
                msg = (
                    f"[PENGINGAT] {device.name} - Daya masih tinggi ({avg_p} W) "
                    f"sejak {_format_time_wib(power_state.since)} WIB"
                )
                if send_alert_notification(msg):
                    sent_messages.append(msg)
                    power_state.last_notified_at = now_ts
                    session.add(
                        Anomaly(
                            device_id=device.id,
                            ts=now_ts,
                            type="power_limit_reminder",
                            severity="warning",
                            details_json=json.dumps({"avg_p": avg_p}),
                            message=msg,
                            notified=1,
                        )
                    )
                    session.commit()
        elif all_recovered and power_state and power_state.state == "active":
            curr_p = round(readings_60s[-1].p, 1)
            msg = f"[PULIH] {device.name} - Daya normal kembali: {curr_p} W"
            if send_alert_notification(msg):
                sent_messages.append(msg)
                power_state.state = "cleared"
                power_state.last_notified_at = now_ts
                power_state.details_json = None
                session.add(
                    Anomaly(
                        device_id=device.id,
                        ts=now_ts,
                        type="power_limit_resolved",
                        severity="info",
                        details_json=json.dumps({"curr_p": curr_p}),
                        message=msg,
                        notified=1,
                    )
                )
                session.commit()

    # --- B. TEGANGAN (VOLTAGE LOW / HIGH) ---
    v_low_state = existing_states.get("voltage_low")
    v_high_state = existing_states.get("voltage_high")

    if len(readings_30s) >= MIN_SAMPLES_VOLTAGE:
        all_low = all(r.v < settings.voltage_min_v for r in readings_30s)
        all_high = all(r.v > settings.voltage_max_v for r in readings_30s)
        all_v_normal = all(
            settings.voltage_recovery_min_v <= r.v <= settings.voltage_recovery_max_v
            for r in readings_30s
        )

        avg_v = round(sum(r.v for r in readings_30s) / len(readings_30s), 1)

        # 1. Voltage Low
        if all_low:
            if not v_low_state or v_low_state.state != "active":
                limit_v = settings.voltage_min_v
                msg = f"[PERINGATAN] {device.name} - Tegangan rendah: {avg_v} V < {limit_v} V"
                if send_alert_notification(msg):
                    sent_messages.append(msg)
                    details = {"avg_v": avg_v, "limit_v": settings.voltage_min_v}
                    if not v_low_state:
                        v_low_state = AlertState(
                            device_id=device.id,
                            alert_type="voltage_low",
                            state="active",
                            since=now_ts,
                            last_notified_at=now_ts,
                            details_json=json.dumps(details),
                        )
                        session.add(v_low_state)
                    else:
                        v_low_state.state = "active"
                        v_low_state.since = now_ts
                        v_low_state.last_notified_at = now_ts
                        v_low_state.details_json = json.dumps(details)

                    session.add(
                        Anomaly(
                            device_id=device.id,
                            ts=now_ts,
                            type="voltage_low",
                            severity="warning",
                            details_json=json.dumps(details),
                            message=msg,
                            notified=1,
                        )
                    )
                    session.commit()
            elif (now_ts - v_low_state.last_notified_at) >= cooldown_seconds:
                msg = (
                    f"[PENGINGAT] {device.name} - Tegangan masih rendah ({avg_v} V) "
                    f"sejak {_format_time_wib(v_low_state.since)} WIB"
                )
                if send_alert_notification(msg):
                    sent_messages.append(msg)
                    v_low_state.last_notified_at = now_ts
                    session.add(
                        Anomaly(
                            device_id=device.id,
                            ts=now_ts,
                            type="voltage_low_reminder",
                            severity="warning",
                            details_json=json.dumps({"avg_v": avg_v}),
                            message=msg,
                            notified=1,
                        )
                    )
                    session.commit()
        elif all_v_normal and v_low_state and v_low_state.state == "active":
            msg = f"[PULIH] {device.name} - Tegangan normal kembali: {avg_v} V"
            if send_alert_notification(msg):
                sent_messages.append(msg)
                v_low_state.state = "cleared"
                v_low_state.last_notified_at = now_ts
                v_low_state.details_json = None
                session.add(
                    Anomaly(
                        device_id=device.id,
                        ts=now_ts,
                        type="voltage_low_resolved",
                        severity="info",
                        details_json=json.dumps({"avg_v": avg_v}),
                        message=msg,
                        notified=1,
                    )
                )
                session.commit()

        # 2. Voltage High
        if all_high:
            if not v_high_state or v_high_state.state != "active":
                limit_v = settings.voltage_max_v
                msg = f"[PERINGATAN] {device.name} - Tegangan tinggi: {avg_v} V > {limit_v} V"
                if send_alert_notification(msg):
                    sent_messages.append(msg)
                    details = {"avg_v": avg_v, "limit_v": settings.voltage_max_v}
                    if not v_high_state:
                        v_high_state = AlertState(
                            device_id=device.id,
                            alert_type="voltage_high",
                            state="active",
                            since=now_ts,
                            last_notified_at=now_ts,
                            details_json=json.dumps(details),
                        )
                        session.add(v_high_state)
                    else:
                        v_high_state.state = "active"
                        v_high_state.since = now_ts
                        v_high_state.last_notified_at = now_ts
                        v_high_state.details_json = json.dumps(details)

                    session.add(
                        Anomaly(
                            device_id=device.id,
                            ts=now_ts,
                            type="voltage_high",
                            severity="warning",
                            details_json=json.dumps(details),
                            message=msg,
                            notified=1,
                        )
                    )
                    session.commit()
            elif (now_ts - v_high_state.last_notified_at) >= cooldown_seconds:
                msg = (
                    f"[PENGINGAT] {device.name} - Tegangan masih tinggi ({avg_v} V) "
                    f"sejak {_format_time_wib(v_high_state.since)} WIB"
                )
                if send_alert_notification(msg):
                    sent_messages.append(msg)
                    v_high_state.last_notified_at = now_ts
                    session.add(
                        Anomaly(
                            device_id=device.id,
                            ts=now_ts,
                            type="voltage_high_reminder",
                            severity="warning",
                            details_json=json.dumps({"avg_v": avg_v}),
                            message=msg,
                            notified=1,
                        )
                    )
                    session.commit()
        elif all_v_normal and v_high_state and v_high_state.state == "active":
            msg = f"[PULIH] {device.name} - Tegangan normal kembali: {avg_v} V"
            if send_alert_notification(msg):
                sent_messages.append(msg)
                v_high_state.state = "cleared"
                v_high_state.last_notified_at = now_ts
                v_high_state.details_json = None
                session.add(
                    Anomaly(
                        device_id=device.id,
                        ts=now_ts,
                        type="voltage_high_resolved",
                        severity="info",
                        details_json=json.dumps({"avg_v": avg_v}),
                        message=msg,
                        notified=1,
                    )
                )
                session.commit()

    return sent_messages


def evaluate_all_alerts(
    session: Session,
    now_ts: Optional[int] = None,
    startup_ts: Optional[int] = None,
) -> list[str]:
    """Mengevaluasi alert untuk seluruh perangkat yang tidak dikecualikan."""
    if now_ts is None:
        now_ts = int(time.time())
    if startup_ts is None:
        startup_ts = get_startup_time()

    # Grace period startup 120 detik
    if (now_ts - startup_ts) < STARTUP_GRACE_PERIOD_SECONDS:
        logger.debug("Alert evaluation skipped: inside startup grace period (%ds remaining)",
                     STARTUP_GRACE_PERIOD_SECONDS - (now_ts - startup_ts))
        return []

    settings = get_settings()
    exclude_prefixes = [
        p.strip()
        for p in settings.alert_exclude_device_prefixes.split(",")
        if p.strip()
    ]

    power_limit_w = _get_setting_int(session, "power_limit_w", settings.default_mcb_watt)
    alert_cooldown_min = _get_setting_int(session, "alert_cooldown_min", 30)

    devices = session.scalars(select(Device)).all()
    all_sent: list[str] = []

    for dev in devices:
        # Kecualikan perangkat ber-prefix terlarang (default 'sim-')
        if any(dev.id.startswith(prefix) for prefix in exclude_prefixes):
            continue

        sent = evaluate_device_alerts(
            session=session,
            device=dev,
            now_ts=now_ts,
            power_limit_w=power_limit_w,
            alert_cooldown_min=alert_cooldown_min,
        )
        all_sent.extend(sent)

    return all_sent


async def run_alert_check_job(
    now_ts: Optional[int] = None,
    startup_ts: Optional[int] = None,
) -> list[str]:
    """Menjalankan pengecekan alert asinkron via to_thread (tidak memblokir ingest)."""
    def _sync_evaluate() -> list[str]:
        with SessionLocal() as session:
            return evaluate_all_alerts(session, now_ts=now_ts, startup_ts=startup_ts)

    return await asyncio.to_thread(_sync_evaluate)
