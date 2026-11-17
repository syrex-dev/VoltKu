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
from app.constants import OFFLINE_THRESHOLD_SECONDS
from app.db import SessionLocal
from app.models import AlertState, Anomaly, Device, Reading, Setting
from app.services.notifier import is_channel_configured, send_alert_notification

logger = logging.getLogger(__name__)
TZ_WIB = ZoneInfo("Asia/Jakarta")

STARTUP_GRACE_PERIOD_SECONDS = 120
MIN_SAMPLES_POWER = 3  # Minimal 3 sampel dalam jendela 60 detik
MIN_SAMPLES_VOLTAGE = 2  # Minimal 2 sampel dalam jendela 30 detik
PUBLISH_INTERVAL_SECONDS = 10
WINDOW_TOLERANCE_SECONDS = 15  # 1.5 * PUBLISH_INTERVAL_SECONDS

_module_startup_time = int(time.time())
_evaluator_tick_count = 0


def check_window_coverage(
    readings: list[Reading],
    window_duration: int,
    now_ts: int,
    session: Session,
    device_id: str,
    threshold_fn,
) -> bool:
    """Memeriksa apakah sampel dalam jendela benar-benar mencakup durasi >= window_duration.

    Syarat:
    1. Sampel tidak boleh kosong.
    2. Sampel tertua <= awal_jendela + 1.5 * interval_publish (15s).
       ATAU jika sampel tertua > awal_jendela + 15s, harus ada sampel sebelum jendela
       (ts < awal_jendela) yang jaraknya <= 15s dan juga melewati ambang (threshold_fn).
    3. Sampel terbaru >= now_ts - 15s (kondisi masih aktif hingga akhir jendela).
    """
    if not readings:
        return False

    window_start = now_ts - window_duration
    oldest_ts = readings[0].ts
    newest_ts = readings[-1].ts

    if newest_ts < (now_ts - WINDOW_TOLERANCE_SECONDS):
        return False

    if oldest_ts <= (window_start + WINDOW_TOLERANCE_SECONDS):
        return True

    prev_reading = session.scalar(
        select(Reading)
        .where(Reading.device_id == device_id, Reading.ts < window_start)
        .order_by(Reading.ts.desc())
        .limit(1)
    )
    if (
        prev_reading
        and (window_start - prev_reading.ts) <= WINDOW_TOLERANCE_SECONDS
        and threshold_fn(prev_reading)
    ):
        return True

    return False


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
    has_channel = is_channel_configured()

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
    # Alert notifikasi offline HANYA terpicu jika data tidak masuk > 120 detik (last_seen_at)
    is_offline = (
        not device.last_seen_at
        or (now_ts - device.last_seen_at) > OFFLINE_THRESHOLD_SECONDS
    )
    offline_state = existing_states.get("offline")

    if is_offline:
        if not offline_state or offline_state.state != "active":
            # Alert baru
            msg = (
                f"[PERINGATAN] {device.name} - Perangkat offline "
                f"(tidak ada data > {OFFLINE_THRESHOLD_SECONDS} detik)"
            )
            evt_key = f"alert:{device.id}:offline:{now_ts}:0"
            if has_channel:
                can_advance = send_alert_notification(msg, event_key=evt_key)
                notified_val = 1
            else:
                can_advance = True
                notified_val = 0

            if can_advance:
                if has_channel:
                    sent_messages.append(msg)
                anom = Anomaly(
                    device_id=device.id,
                    ts=now_ts,
                    type="offline",
                    severity="warning",
                    details_json=json.dumps({"last_seen_at": device.last_seen_at}),
                    message=msg,
                    notified=notified_val,
                )
                session.add(anom)
                session.flush()

                details = {
                    "last_seen_at": device.last_seen_at,
                    "anomaly_id": anom.id,
                    "reminder_seq": 0,
                }
                if not offline_state:
                    offline_state = AlertState(
                        device_id=device.id,
                        alert_type="offline",
                        state="active",
                        since=now_ts,
                        last_notified_at=now_ts if has_channel else 0,
                        details_json=json.dumps(details),
                    )
                    session.add(offline_state)
                else:
                    offline_state.state = "active"
                    offline_state.since = now_ts
                    offline_state.last_notified_at = now_ts if has_channel else 0
                    offline_state.details_json = json.dumps(details)

                session.commit()
        elif (
            has_channel
            and offline_state.last_notified_at
            and (now_ts - offline_state.last_notified_at) >= cooldown_seconds
        ):
            # Pengingat setelah cooldown HANYA jika ada kanal
            msg = (
                f"[PENGINGAT] {device.name} - Perangkat masih offline "
                f"sejak {_format_time_wib(offline_state.since)} WIB"
            )
            try:
                d_prev = json.loads(offline_state.details_json or "{}")
            except Exception:
                d_prev = {}
            rem_seq = d_prev.get("reminder_seq", 0) + 1
            d_prev["reminder_seq"] = rem_seq
            offline_state.details_json = json.dumps(d_prev)
            evt_key = f"alert:{device.id}:offline:{offline_state.since}:{rem_seq}"
            if send_alert_notification(msg, event_key=evt_key):
                sent_messages.append(msg)
                offline_state.last_notified_at = now_ts
                session.commit()
    else:
        # Perangkat online: kirim pesan pulih
        if offline_state and offline_state.state == "active":
            msg = f"[PULIH] {device.name} - Perangkat online kembali"
            evt_key = f"recovery:{device.id}:offline:{now_ts}"
            if has_channel:
                if send_alert_notification(msg, event_key=evt_key):
                    sent_messages.append(msg)
            offline_state.state = "cleared"
            if has_channel:
                offline_state.last_notified_at = now_ts

                # Catat pemulihan di details_json pada episode anomali yang sama
                anomaly_id = None
                if offline_state.details_json:
                    try:
                        st_data = json.loads(offline_state.details_json)
                        anomaly_id = st_data.get("anomaly_id")
                    except Exception:
                        pass
                active_anom = None
                if anomaly_id:
                    active_anom = session.get(Anomaly, anomaly_id)
                if not active_anom:
                    active_anom = session.scalar(
                        select(Anomaly)
                        .where(Anomaly.device_id == device.id, Anomaly.type == "offline")
                        .order_by(Anomaly.ts.desc())
                        .limit(1)
                    )
                if active_anom:
                    try:
                        d = json.loads(active_anom.details_json or "{}")
                    except Exception:
                        d = {}
                    d["resolved_at"] = now_ts
                    d["online_at"] = now_ts
                    active_anom.details_json = json.dumps(d)

                offline_state.details_json = None
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
        power_covered = check_window_coverage(
            readings=readings_60s,
            window_duration=60,
            now_ts=now_ts,
            session=session,
            device_id=device.id,
            threshold_fn=lambda r: r.p > power_limit_w,
        )

        if all_above_limit and power_covered:
            avg_p = round(sum(r.p for r in readings_60s) / len(readings_60s), 1)
            if not power_state or power_state.state != "active":
                msg = (
                    f"[PERINGATAN] {device.name} - Daya melebihi batas wajar: "
                    f"{avg_p} W > {power_limit_w} W"
                )
                evt_key = f"alert:{device.id}:power_limit:{now_ts}:0"
                if has_channel:
                    can_advance = send_alert_notification(msg, event_key=evt_key)
                    notified_val = 1
                else:
                    can_advance = True
                    notified_val = 0

                if can_advance:
                    if has_channel:
                        sent_messages.append(msg)
                    details = {
                        "avg_p": avg_p,
                        "limit_w": power_limit_w,
                        "samples": len(readings_60s),
                        "reminder_seq": 0,
                    }
                    anom = Anomaly(
                        device_id=device.id,
                        ts=now_ts,
                        type="power_limit",
                        severity="warning",
                        details_json=json.dumps(details),
                        message=msg,
                        notified=notified_val,
                    )
                    session.add(anom)
                    session.flush()

                    details["anomaly_id"] = anom.id
                    if not power_state:
                        power_state = AlertState(
                            device_id=device.id,
                            alert_type="power_limit",
                            state="active",
                            since=now_ts,
                            last_notified_at=now_ts if has_channel else 0,
                            details_json=json.dumps(details),
                        )
                        session.add(power_state)
                    else:
                        power_state.state = "active"
                        power_state.since = now_ts
                        power_state.last_notified_at = now_ts if has_channel else 0
                        power_state.details_json = json.dumps(details)

                    session.commit()
            elif (
                has_channel
                and power_state.last_notified_at
                and (now_ts - power_state.last_notified_at) >= cooldown_seconds
            ):
                msg = (
                    f"[PENGINGAT] {device.name} - Daya masih tinggi ({avg_p} W) "
                    f"sejak {_format_time_wib(power_state.since)} WIB"
                )
                try:
                    d_prev = json.loads(power_state.details_json or "{}")
                except Exception:
                    d_prev = {}
                rem_seq = d_prev.get("reminder_seq", 0) + 1
                d_prev["reminder_seq"] = rem_seq
                power_state.details_json = json.dumps(d_prev)
                evt_key = f"alert:{device.id}:power_limit:{power_state.since}:{rem_seq}"
                if send_alert_notification(msg, event_key=evt_key):
                    sent_messages.append(msg)
                    power_state.last_notified_at = now_ts
                    session.commit()
        elif all_recovered and power_state and power_state.state == "active":
            curr_p = round(readings_60s[-1].p, 1)
            msg = f"[PULIH] {device.name} - Daya normal kembali: {curr_p} W"
            evt_key = f"recovery:{device.id}:power_limit:{now_ts}"
            if has_channel:
                if send_alert_notification(msg, event_key=evt_key):
                    sent_messages.append(msg)
            power_state.state = "cleared"
            if has_channel:
                power_state.last_notified_at = now_ts

                # Catat pemulihan di details_json pada episode anomali yang sama
                anomaly_id = None
                if power_state.details_json:
                    try:
                        st_data = json.loads(power_state.details_json)
                        anomaly_id = st_data.get("anomaly_id")
                    except Exception:
                        pass
                active_anom = None
                if anomaly_id:
                    active_anom = session.get(Anomaly, anomaly_id)
                if not active_anom:
                    active_anom = session.scalar(
                        select(Anomaly)
                        .where(Anomaly.device_id == device.id, Anomaly.type == "power_limit")
                        .order_by(Anomaly.ts.desc())
                        .limit(1)
                    )
                if active_anom:
                    try:
                        d = json.loads(active_anom.details_json or "{}")
                    except Exception:
                        d = {}
                    d["resolved_at"] = now_ts
                    d["resolved_p_w"] = curr_p
                    active_anom.details_json = json.dumps(d)

                power_state.details_json = None
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

        v_low_covered = check_window_coverage(
            readings=readings_30s,
            window_duration=30,
            now_ts=now_ts,
            session=session,
            device_id=device.id,
            threshold_fn=lambda r: r.v < settings.voltage_min_v,
        )
        v_high_covered = check_window_coverage(
            readings=readings_30s,
            window_duration=30,
            now_ts=now_ts,
            session=session,
            device_id=device.id,
            threshold_fn=lambda r: r.v > settings.voltage_max_v,
        )

        # 1. Voltage Low
        if all_low and v_low_covered:
            if not v_low_state or v_low_state.state != "active":
                limit_v = settings.voltage_min_v
                msg = f"[PERINGATAN] {device.name} - Tegangan rendah: {avg_v} V < {limit_v} V"
                evt_key = f"alert:{device.id}:voltage_low:{now_ts}:0"
                if has_channel:
                    can_advance = send_alert_notification(msg, event_key=evt_key)
                    notified_val = 1
                else:
                    can_advance = True
                    notified_val = 0

                if can_advance:
                    if has_channel:
                        sent_messages.append(msg)
                    details = {
                        "sub_type": "low",
                        "avg_v": avg_v,
                        "limit_v": settings.voltage_min_v,
                        "reminder_seq": 0,
                    }
                    anom = Anomaly(
                        device_id=device.id,
                        ts=now_ts,
                        type="voltage",
                        severity="warning",
                        details_json=json.dumps(details),
                        message=msg,
                        notified=notified_val,
                    )
                    session.add(anom)
                    session.flush()

                    details["anomaly_id"] = anom.id
                    if not v_low_state:
                        v_low_state = AlertState(
                            device_id=device.id,
                            alert_type="voltage_low",
                            state="active",
                            since=now_ts,
                            last_notified_at=now_ts if has_channel else 0,
                            details_json=json.dumps(details),
                        )
                        session.add(v_low_state)
                    else:
                        v_low_state.state = "active"
                        v_low_state.since = now_ts
                        v_low_state.last_notified_at = now_ts if has_channel else 0
                        v_low_state.details_json = json.dumps(details)

                    session.commit()
            elif (
                has_channel
                and v_low_state.last_notified_at
                and (now_ts - v_low_state.last_notified_at) >= cooldown_seconds
            ):
                msg = (
                    f"[PENGINGAT] {device.name} - Tegangan masih rendah ({avg_v} V) "
                    f"sejak {_format_time_wib(v_low_state.since)} WIB"
                )
                try:
                    d_prev = json.loads(v_low_state.details_json or "{}")
                except Exception:
                    d_prev = {}
                rem_seq = d_prev.get("reminder_seq", 0) + 1
                d_prev["reminder_seq"] = rem_seq
                v_low_state.details_json = json.dumps(d_prev)
                evt_key = f"alert:{device.id}:voltage_low:{v_low_state.since}:{rem_seq}"
                if send_alert_notification(msg, event_key=evt_key):
                    sent_messages.append(msg)
                    v_low_state.last_notified_at = now_ts
                    session.commit()
        elif all_v_normal and v_low_state and v_low_state.state == "active":
            msg = f"[PULIH] {device.name} - Tegangan normal kembali: {avg_v} V"
            evt_key = f"recovery:{device.id}:voltage_low:{now_ts}"
            if has_channel:
                if send_alert_notification(msg, event_key=evt_key):
                    sent_messages.append(msg)
            v_low_state.state = "cleared"
            if has_channel:
                v_low_state.last_notified_at = now_ts

                # Catat pemulihan di details_json pada episode anomali yang sama
                anomaly_id = None
                if v_low_state.details_json:
                    try:
                        st_data = json.loads(v_low_state.details_json)
                        anomaly_id = st_data.get("anomaly_id")
                    except Exception:
                        pass
                active_anom = None
                if anomaly_id:
                    active_anom = session.get(Anomaly, anomaly_id)
                if not active_anom:
                    active_anom = session.scalar(
                        select(Anomaly)
                        .where(Anomaly.device_id == device.id, Anomaly.type == "voltage")
                        .order_by(Anomaly.ts.desc())
                        .limit(1)
                    )
                if active_anom:
                    try:
                        d = json.loads(active_anom.details_json or "{}")
                    except Exception:
                        d = {}
                    d["resolved_at"] = now_ts
                    d["resolved_v"] = avg_v
                    active_anom.details_json = json.dumps(d)

                v_low_state.details_json = None
                session.commit()

        # 2. Voltage High
        if all_high and v_high_covered:
            if not v_high_state or v_high_state.state != "active":
                limit_v = settings.voltage_max_v
                msg = f"[PERINGATAN] {device.name} - Tegangan tinggi: {avg_v} V > {limit_v} V"
                evt_key = f"alert:{device.id}:voltage_high:{now_ts}:0"
                if has_channel:
                    can_advance = send_alert_notification(msg, event_key=evt_key)
                    notified_val = 1
                else:
                    can_advance = True
                    notified_val = 0

                if can_advance:
                    if has_channel:
                        sent_messages.append(msg)
                    details = {
                        "sub_type": "high",
                        "avg_v": avg_v,
                        "limit_v": settings.voltage_max_v,
                        "reminder_seq": 0,
                    }
                    anom = Anomaly(
                        device_id=device.id,
                        ts=now_ts,
                        type="voltage",
                        severity="warning",
                        details_json=json.dumps(details),
                        message=msg,
                        notified=notified_val,
                    )
                    session.add(anom)
                    session.flush()

                    details["anomaly_id"] = anom.id
                    if not v_high_state:
                        v_high_state = AlertState(
                            device_id=device.id,
                            alert_type="voltage_high",
                            state="active",
                            since=now_ts,
                            last_notified_at=now_ts if has_channel else 0,
                            details_json=json.dumps(details),
                        )
                        session.add(v_high_state)
                    else:
                        v_high_state.state = "active"
                        v_high_state.since = now_ts
                        v_high_state.last_notified_at = now_ts if has_channel else 0
                        v_high_state.details_json = json.dumps(details)

                    session.commit()
            elif (
                has_channel
                and v_high_state.last_notified_at
                and (now_ts - v_high_state.last_notified_at) >= cooldown_seconds
            ):
                msg = (
                    f"[PENGINGAT] {device.name} - Tegangan masih tinggi ({avg_v} V) "
                    f"sejak {_format_time_wib(v_high_state.since)} WIB"
                )
                try:
                    d_prev = json.loads(v_high_state.details_json or "{}")
                except Exception:
                    d_prev = {}
                rem_seq = d_prev.get("reminder_seq", 0) + 1
                d_prev["reminder_seq"] = rem_seq
                v_high_state.details_json = json.dumps(d_prev)
                evt_key = f"alert:{device.id}:voltage_high:{v_high_state.since}:{rem_seq}"
                if send_alert_notification(msg, event_key=evt_key):
                    sent_messages.append(msg)
                    v_high_state.last_notified_at = now_ts
                    session.commit()
        elif all_v_normal and v_high_state and v_high_state.state == "active":
            msg = f"[PULIH] {device.name} - Tegangan normal kembali: {avg_v} V"
            evt_key = f"recovery:{device.id}:voltage_high:{now_ts}"
            if has_channel:
                if send_alert_notification(msg, event_key=evt_key):
                    sent_messages.append(msg)
            v_high_state.state = "cleared"
            if has_channel:
                v_high_state.last_notified_at = now_ts

                # Catat pemulihan di details_json pada episode anomali yang sama
                anomaly_id = None
                if v_high_state.details_json:
                    try:
                        st_data = json.loads(v_high_state.details_json)
                        anomaly_id = st_data.get("anomaly_id")
                    except Exception:
                        pass
                active_anom = None
                if anomaly_id:
                    active_anom = session.get(Anomaly, anomaly_id)
                if not active_anom:
                    active_anom = session.scalar(
                        select(Anomaly)
                        .where(Anomaly.device_id == device.id, Anomaly.type == "voltage")
                        .order_by(Anomaly.ts.desc())
                        .limit(1)
                    )
                if active_anom:
                    try:
                        d = json.loads(active_anom.details_json or "{}")
                    except Exception:
                        d = {}
                    d["resolved_at"] = now_ts
                    d["resolved_v"] = avg_v
                    active_anom.details_json = json.dumps(d)

                v_high_state.details_json = None
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
    global _evaluator_tick_count
    _evaluator_tick_count += 1

    devices = session.scalars(select(Device)).all()
    if _evaluator_tick_count == 1 or _evaluator_tick_count % 10 == 0:
        logger.info(
            "[EVALUATOR_TICK #%d] Evaluasi alert berjalan (devices=%d)",
            _evaluator_tick_count,
            len(devices),
        )

    # Jalankan pemrosesan antrean retry chat yang gagal sebelumnya
    try:
        from app.services.bot import process_chat_retry_queue_sync
        process_chat_retry_queue_sync()
    except Exception as e:
        logger.debug("Retry queue process skipped/error: %s", e)

    exclude_prefixes = [
        p.strip()
        for p in settings.alert_exclude_device_prefixes.split(",")
        if p.strip()
    ]

    power_limit_w = _get_setting_int(session, "power_limit_w", settings.default_mcb_watt)
    alert_cooldown_min = _get_setting_int(session, "alert_cooldown_min", 30)

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
