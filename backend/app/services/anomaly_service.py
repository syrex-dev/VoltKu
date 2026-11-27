"""
backend/app/services/anomaly_service.py
Orkestrator runtime untuk mesin anomali L2 (Baseline Spike) dan L3 (Beban Dasar Malam).
Memanfaatkan pure engine di app.services.anomaly_engine tanpa efek samping di engine murni.
"""

import asyncio
import json
import logging
import statistics
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import AlertState, Anomaly, Device, Reading, Setting, User, UserSetting
from app.services.anomaly_engine import AnomalyEngine, Window5m
from app.services.notifier import is_channel_configured, send_alert_notification
from app.services.push_notifier import notify_device_owner
from app.services.timezone_utils import normalize_timezone_name, resolve_zoneinfo

logger = logging.getLogger(__name__)
_default_engine = AnomalyEngine()
_DEFAULT_TZ = ZoneInfo("Asia/Jakarta")


def _aggregate_readings_to_windows(
    readings: list[Reading],
    tz: ZoneInfo,
) -> list[Window5m]:
    """Kelompokkan bacaan mentah ke jendela 5 menit (kelipatan 300s) berdasar zona waktu aktif."""
    buckets: dict[int, list[float]] = defaultdict(list)
    for r in readings:
        w_start = (int(r.ts) // 300) * 300
        buckets[w_start].append(float(r.p))

    windows: list[Window5m] = []
    for w_start in sorted(buckets):
        vals = buckets[w_start]
        dt = datetime.fromtimestamp(w_start, tz=tz)
        windows.append(
            Window5m(
                start_ts=w_start,
                sample_count=len(vals),
                p_avg=sum(vals) / len(vals),
                p_max=max(vals),
                p_min=min(vals),
                hour_wib=dt.hour,
                date_wib=dt.strftime("%Y-%m-%d"),
                is_weekend=(dt.weekday() >= 5),
            )
        )
    return windows


def _read_alert_details(state_row: Optional[AlertState]) -> dict:
    if not state_row or not state_row.details_json:
        return {}
    try:
        parsed = json.loads(state_row.details_json)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _get_user_pref_map(session: Session) -> dict[tuple[int, str], str]:
    out: dict[tuple[int, str], str] = {}
    rows = session.scalars(
        select(UserSetting).where(
            UserSetting.key.in_(("alert_cooldown_min", "report_timezone"))
        )
    ).all()
    for row in rows:
        out[(int(row.user_id), str(row.key))] = str(row.value)
    return out


def _evaluate_device_l2_l3(
    session: Session,
    device: Device,
    *,
    now_ts: int,
    cooldown_min: int,
    tz: ZoneInfo,
    engine: AnomalyEngine,
) -> list[str]:
    sent_messages: list[str] = []
    cutoff_14d = now_ts - (14 * 86400)
    readings = session.scalars(
        select(Reading)
        .where(
            Reading.device_id == device.id,
            Reading.ts >= cutoff_14d,
            Reading.ts <= now_ts,
        )
        .order_by(Reading.ts.asc())
    ).all()
    if not readings:
        return sent_messages

    windows = _aggregate_readings_to_windows(readings, tz)
    current_bucket_start = (now_ts // 300) * 300
    completed_windows = [
        w for w in windows if w.start_ts < current_bucket_start and w.is_complete
    ]
    if not completed_windows:
        return sent_messages

    has_channel = is_channel_configured()

    # --- 1. L2: Baseline Robust Z-Score pada jendela 5m terakhir yang lengkap ---
    latest_w = completed_windows[-1]
    if (now_ts - latest_w.start_ts) <= 900:  # Maks 15 menit lalu agar tidak memicu data basi
        history_w = [w for w in completed_windows if w.start_ts < latest_w.start_ts]
        l2_state = session.scalar(
            select(AlertState).where(
                AlertState.device_id == device.id,
                AlertState.alert_type == "anomaly_l2",
            )
        )
        prev_details = _read_alert_details(l2_state)
        last_eval_ts = int(prev_details.get("last_window_ts") or 0)
        prev_consec = int(prev_details.get("consecutive_count") or 0)

        if latest_w.start_ts > last_eval_ts:
            res = engine.evaluate_window(
                current_window=latest_w,
                history_windows=history_w,
                consecutive_candidates=prev_consec,
            )
            next_details = {
                "last_window_ts": latest_w.start_ts,
                "consecutive_count": res.consecutive_count,
                "z_score": round(res.z_score, 2),
                "baseline_median": round(res.baseline_median, 1),
            }
            if l2_state is None:
                l2_state = AlertState(
                    device_id=device.id,
                    alert_type="anomaly_l2",
                    state="cleared",
                    since=now_ts,
                    last_notified_at=0,
                    details_json=json.dumps(next_details),
                )
                session.add(l2_state)
            else:
                l2_state.details_json = json.dumps(next_details)

            cooldown_sec = max(5, int(cooldown_min)) * 60
            in_cooldown = (
                l2_state.last_notified_at > 0
                and (now_ts - l2_state.last_notified_at) < cooldown_sec
            )
            if res.is_anomaly_alert and not in_cooldown:
                msg = (
                    f"[ANOMALI L2] {device.name} - Lonjakan beban tak biasa "
                    f"{res.window.p_avg:.0f} W (baseline normal {res.baseline_median:.0f} W, "
                    f"Z={res.z_score:.1f})"
                )
                evt_key = f"l2:{device.id}:{latest_w.start_ts}"
                tg_ok = send_alert_notification(msg, event_key=evt_key) if has_channel else False
                if tg_ok:
                    sent_messages.append(msg)

                anom = Anomaly(
                    device_id=device.id,
                    ts=latest_w.start_ts,
                    type="l2_spike",
                    severity="warning",
                    details_json=json.dumps(
                        {
                            "p_avg": round(res.window.p_avg, 1),
                            "baseline_median": round(res.baseline_median, 1),
                            "z_score": round(res.z_score, 2),
                            "delta_w": round(res.delta_w, 1),
                            "bucket_type": res.bucket_type,
                        }
                    ),
                    message=msg[:256],
                    notified=1 if tg_ok else 0,
                )
                session.add(anom)
                l2_state.state = "active"
                l2_state.since = latest_w.start_ts
                l2_state.last_notified_at = now_ts
                session.commit()

                try:
                    notify_device_owner(
                        session,
                        device=device,
                        title=f"Lonjakan Daya Tak Biasa · {device.name}",
                        body=msg,
                        category="anomaly",
                        severity="warning",
                        data={"alert_type": "l2_spike"},
                        event_key=evt_key,
                        now_ts=now_ts,
                    )
                except Exception as exc:
                    logger.debug("Push notif L2 gagal untuk %s: %s", device.id, exc)
            else:
                if not res.is_candidate and l2_state.state == "active":
                    l2_state.state = "cleared"
                session.commit()

    # --- 2. L3: Beban Dasar Malam (00:00 - 05:00 lokal, dievaluasi setelah jam 05:00) ---
    now_local = datetime.fromtimestamp(now_ts, tz=tz)
    if now_local.hour >= 5:
        today_str = now_local.strftime("%Y-%m-%d")
        l3_state = session.scalar(
            select(AlertState).where(
                AlertState.device_id == device.id,
                AlertState.alert_type == "anomaly_l3",
            )
        )
        l3_details = _read_alert_details(l3_state)
        if l3_details.get("last_checked_date") != today_str:
            night_by_date: dict[str, list[Window5m]] = defaultdict(list)
            for w in completed_windows:
                if 0 <= w.hour_wib < 5:
                    night_by_date[w.date_wib].append(w)

            today_night = night_by_date.get(today_str, [])
            past_medians: list[float] = []
            for d_offset in range(1, 8):
                d_prev = (now_local.date() - timedelta(days=d_offset)).strftime("%Y-%m-%d")
                prev_wins = night_by_date.get(d_prev, [])
                if len(prev_wins) >= 12:
                    past_medians.append(statistics.median([pw.p_avg for pw in prev_wins]))

            is_alert, today_base, ref_base, reason = engine.evaluate_l3_night_baseload(
                today_night_windows=today_night,
                past_7days_night_baseloads=past_medians,
            )
            new_l3_details = {
                "last_checked_date": today_str,
                "today_base_w": round(today_base, 1) if today_base is not None else None,
                "ref_base_w": round(ref_base, 1) if ref_base is not None else None,
            }
            if l3_state is None:
                l3_state = AlertState(
                    device_id=device.id,
                    alert_type="anomaly_l3",
                    state="active" if is_alert else "cleared",
                    since=now_ts,
                    last_notified_at=now_ts if is_alert else 0,
                    details_json=json.dumps(new_l3_details),
                )
                session.add(l3_state)
            else:
                l3_state.state = "active" if is_alert else "cleared"
                l3_state.details_json = json.dumps(new_l3_details)
                if is_alert:
                    l3_state.since = now_ts
                    l3_state.last_notified_at = now_ts

            if is_alert and today_base is not None and ref_base is not None:
                msg = (
                    f"[ANOMALI L3] {device.name} - Beban dasar malam naik: "
                    f"{today_base:.0f} W (normal 7h: {ref_base:.0f} W · {reason})"
                )
                evt_key = f"l3:{device.id}:{today_str}"
                tg_ok = send_alert_notification(msg, event_key=evt_key) if has_channel else False
                if tg_ok:
                    sent_messages.append(msg)

                session.add(
                    Anomaly(
                        device_id=device.id,
                        ts=now_ts,
                        type="l3_baseload",
                        severity="warning",
                        details_json=json.dumps(
                            {
                                "today_base_w": round(today_base, 1),
                                "ref_base_w": round(ref_base, 1),
                                "reason": reason,
                            }
                        ),
                        message=msg[:256],
                        notified=1 if tg_ok else 0,
                    )
                )
                session.commit()
                try:
                    notify_device_owner(
                        session,
                        device=device,
                        title=f"Beban Dasar Malam Naik · {device.name}",
                        body=msg,
                        category="anomaly",
                        severity="warning",
                        data={"alert_type": "l3_baseload", "date": today_str},
                        event_key=evt_key,
                        now_ts=now_ts,
                    )
                except Exception as exc:
                    logger.debug("Push notif L3 gagal untuk %s: %s", device.id, exc)
            else:
                session.commit()

    return sent_messages


def evaluate_all_l2_l3_anomalies(
    session: Session,
    now_ts: Optional[int] = None,
    engine: Optional[AnomalyEngine] = None,
) -> list[str]:
    """Evaluasi anomali L2/L3 untuk perangkat milik akun berfitur anomaly_advanced / operator."""
    eff_now = int(now_ts if now_ts is not None else time.time())
    eff_engine = engine or _default_engine
    settings = get_settings()
    exclude_prefixes = [
        p.strip() for p in settings.alert_exclude_device_prefixes.split(",") if p.strip()
    ]

    global_cooldown_row = session.scalar(
        select(Setting.value).where(Setting.key == "alert_cooldown_min")
    )
    global_tz_row = session.scalar(select(Setting.value).where(Setting.key == "report_timezone"))
    try:
        global_cooldown = int(global_cooldown_row) if global_cooldown_row is not None else 30
    except ValueError:
        global_cooldown = 30
    global_tz_name = normalize_timezone_name(global_tz_row)

    from app.services.app_config import get_app_config_map
    from app.services.plans import resolve_user_plan

    user_prefs = _get_user_pref_map(session)
    cfg_map = get_app_config_map(session)

    devices = session.scalars(select(Device)).all()
    owner_ids = {int(d.owner_user_id) for d in devices if d.owner_user_id is not None}
    users_by_id = (
        {
            u.id: u
            for u in session.scalars(select(User).where(User.id.in_(owner_ids))).all()
        }
        if owner_ids
        else {}
    )
    user_adv_allowed: dict[int, bool] = {}
    for uid, u_obj in users_by_id.items():
        plan = resolve_user_plan(session, u_obj, cfg_map)
        user_adv_allowed[uid] = (not plan["freemium_enabled"]) or bool(
            plan["limits"].get("anomaly_advanced", False)
        )

    all_sent: list[str] = []
    for dev in devices:
        if any(dev.id.startswith(p) for p in exclude_prefixes):
            continue
        uid = getattr(dev, "owner_user_id", None)
        if uid is not None and not user_adv_allowed.get(int(uid), False):
            continue

        raw_cd = user_prefs.get((int(uid), "alert_cooldown_min")) if uid is not None else None
        try:
            dev_cooldown = int(raw_cd) if raw_cd is not None else global_cooldown
        except ValueError:
            dev_cooldown = global_cooldown

        raw_tz = user_prefs.get((int(uid), "report_timezone")) if uid is not None else None
        dev_tz = resolve_zoneinfo(normalize_timezone_name(raw_tz or global_tz_name))

        all_sent.extend(
            _evaluate_device_l2_l3(
                session,
                dev,
                now_ts=eff_now,
                cooldown_min=dev_cooldown,
                tz=dev_tz,
                engine=eff_engine,
            )
        )
    return all_sent


async def run_l2_l3_anomaly_job(now_ts: Optional[int] = None) -> list[str]:
    """Menjalankan evaluasi anomali L2/L3 asinkron via thread pool."""

    def _sync() -> list[str]:
        with SessionLocal() as session:
            return evaluate_all_l2_l3_anomalies(session, now_ts=now_ts)

    return await asyncio.to_thread(_sync)
