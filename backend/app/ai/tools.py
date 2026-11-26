import time as time_mod
from datetime import datetime, time, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import OFFLINE_THRESHOLD_SECONDS
from app.models import Anomaly, Device, HourlyStat, Reading
from app.mqtt_ingest import get_device_status
from app.services.reports import calculate_device_forecast, calculate_device_summary

TZ_WIB = ZoneInfo("Asia/Jakarta")
MAX_TOOL_RANGE_DAYS = 90

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "list_devices",
        "description": "Mengambil daftar perangkat panel listrik milik pengguna.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_current",
        "description": (
            "Mengambil pembacaan listrik terakhir (watt, volt, ampere, status) perangkat."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "ID perangkat opsional."}
            },
        },
    },
    {
        "name": "get_summary",
        "description": (
            "Menghitung ringkasan kWh, biaya Rupiah, rata-rata watt, dan puncak periode."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "range": {
                    "type": "string",
                    "description": "today, yesterday, this_week, last_week, this_month, last_month",
                },
                "from_ts": {"type": "integer", "description": "Epoch UTC mulai opsional."},
                "to_ts": {"type": "integer", "description": "Epoch UTC akhir opsional."},
                "device_id": {"type": "string", "description": "ID perangkat opsional."},
            },
        },
    },
    {
        "name": "compare_periods",
        "description": (
            "Membandingkan kWh dan biaya antara dua rentang waktu beserta jam selisih terbesar."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "a_from": {"type": "integer", "description": "Epoch UTC mulai periode A."},
                "a_to": {"type": "integer", "description": "Epoch UTC akhir periode A."},
                "b_from": {"type": "integer", "description": "Epoch UTC mulai periode B."},
                "b_to": {"type": "integer", "description": "Epoch UTC akhir periode B."},
                "device_id": {"type": "string", "description": "ID perangkat opsional."},
            },
            "required": ["a_from", "a_to", "b_from", "b_to"],
        },
    },
    {
        "name": "get_hourly_profile",
        "description": "Mengambil rata-rata daya per jam (0-23 WIB) pada suatu periode.",
        "parameters": {
            "type": "object",
            "properties": {
                "range": {
                    "type": "string",
                    "description": "today, yesterday, this_week, last_week, this_month",
                },
                "device_id": {"type": "string", "description": "ID perangkat opsional."},
            },
        },
    },
    {
        "name": "get_anomalies",
        "description": "Mengambil daftar peringatan dan anomali listrik pada suatu periode.",
        "parameters": {
            "type": "object",
            "properties": {
                "range": {
                    "type": "string",
                    "description": "today, yesterday, this_week, this_month",
                },
                "device_id": {"type": "string", "description": "ID perangkat opsional."},
            },
        },
    },
    {
        "name": "get_forecast",
        "description": "Mengambil proyeksi total kWh dan biaya listrik akhir bulan.",
        "parameters": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "ID perangkat opsional."}
            },
        },
    },
]


def _accessible_devices(
    session: Session,
    user_id: Optional[int],
    is_admin: bool,
    device_id: Optional[str] = None,
) -> list[Device]:
    stmt = select(Device).where(~Device.id.startswith("sim-")).order_by(Device.id.asc())
    if not is_admin:
        if user_id is None:
            return []
        stmt = stmt.where(Device.owner_user_id == user_id)
    if device_id:
        stmt = stmt.where(Device.id == device_id.strip())
    return list(session.scalars(stmt).all())


def _resolve_range_bounds(
    range_name: Optional[str],
    now_dt: Optional[datetime] = None,
) -> tuple[int, int]:
    now_wib = now_dt.astimezone(TZ_WIB) if now_dt else datetime.now(tz=TZ_WIB)
    r = (range_name or "today").strip().lower()
    today_start = datetime.combine(now_wib.date(), time(0, 0, 0), tzinfo=TZ_WIB)

    if r == "today":
        return int(today_start.timestamp()), int(now_wib.timestamp())
    if r == "yesterday":
        y_start = today_start - timedelta(days=1)
        return int(y_start.timestamp()), int(today_start.timestamp()) - 1
    if r == "this_week":
        w_start = today_start - timedelta(days=now_wib.weekday())
        return int(w_start.timestamp()), int(now_wib.timestamp())
    if r == "last_week":
        this_w_start = today_start - timedelta(days=now_wib.weekday())
        last_w_start = this_w_start - timedelta(days=7)
        return int(last_w_start.timestamp()), int(this_w_start.timestamp()) - 1
    if r == "this_month":
        m_start = datetime(now_wib.year, now_wib.month, 1, 0, 0, 0, tzinfo=TZ_WIB)
        return int(m_start.timestamp()), int(now_wib.timestamp())
    if r == "last_month":
        m_start = datetime(now_wib.year, now_wib.month, 1, 0, 0, 0, tzinfo=TZ_WIB)
        last_m_end = m_start - timedelta(seconds=1)
        last_m_start = datetime(last_m_end.year, last_m_end.month, 1, 0, 0, 0, tzinfo=TZ_WIB)
        return int(last_m_start.timestamp()), int(last_m_end.timestamp())
    raise ValueError(f"Rentang waktu '{range_name}' tidak dikenal.")


def _validate_bounds(from_ts: int, to_ts: int) -> None:
    if from_ts > to_ts:
        raise ValueError("Parameter waktu mulai lebih besar dari waktu selesai.")
    if (to_ts - from_ts) > MAX_TOOL_RANGE_DAYS * 86400:
        raise ValueError("Rentang waktu melebihi batas maksimal 90 hari.")


def execute_tool(
    session: Session,
    tool_name: str,
    args: dict[str, Any],
    *,
    user_id: Optional[int],
    is_admin: bool,
    now_dt: Optional[datetime] = None,
) -> dict[str, Any]:
    """Menjalankan salah satu dari 7 tool deterministik dengan validasi akses dan batas 90 hari."""
    now_epoch = int((now_dt or datetime.now(tz=TZ_WIB)).timestamp())
    device_id = args.get("device_id")

    if tool_name == "list_devices":
        devs = _accessible_devices(session, user_id, is_admin)
        return {
            "devices": [
                {
                    "id": d.id,
                    "name": d.name or d.id,
                    "location": d.location,
                    "mcb_watt": d.mcb_watt,
                    "status": get_device_status(
                        d, now_utc=now_epoch, threshold_seconds=OFFLINE_THRESHOLD_SECONDS
                    ),
                }
                for d in devs
            ]
        }

    devs = _accessible_devices(session, user_id, is_admin, device_id=device_id)
    if not devs:
        return {"error": "Perangkat tidak ditemukan atau Anda tidak memiliki akses."}

    if tool_name == "get_current":
        items = []
        for d in devs:
            latest = session.scalar(
                select(Reading)
                .where(Reading.device_id == d.id)
                .order_by(Reading.ts.desc())
                .limit(1)
            )
            st = get_device_status(
                d, now_utc=now_epoch, threshold_seconds=OFFLINE_THRESHOLD_SECONDS
            )
            if latest:
                t_wib = datetime.fromtimestamp(latest.ts, tz=TZ_WIB).strftime("%d/%m/%Y %H:%M:%S")
                items.append(
                    {
                        "device_id": d.id,
                        "name": d.name or d.id,
                        "status": st,
                        "time_wib": t_wib,
                        "p_w": round(latest.p, 1),
                        "v": round(latest.v, 1),
                        "i": round(latest.i, 3),
                        "pf": round(latest.pf, 2),
                    }
                )
            else:
                items.append(
                    {"device_id": d.id, "name": d.name or d.id, "status": st, "data": None}
                )
        return {"devices": items}

    if tool_name == "get_summary":
        range_arg = args.get("range")
        from_ts = args.get("from_ts")
        to_ts = args.get("to_ts")
        if from_ts is not None and to_ts is not None:
            f_ts, t_ts = int(from_ts), int(to_ts)
        else:
            f_ts, t_ts = _resolve_range_bounds(range_arg or "today", now_dt=now_dt)
        _validate_bounds(f_ts, t_ts)

        summaries = []
        for d in devs:
            s = calculate_device_summary(
                session, d.id, from_ts=f_ts, to_ts=t_ts, now_dt=now_dt
            )
            peak_ts = s.get("peak_ts")
            peak_hour_wib = (
                datetime.fromtimestamp(peak_ts, tz=TZ_WIB).strftime("%d/%m %H:%M WIB")
                if peak_ts
                else None
            )
            summaries.append(
                {
                    "device_id": d.id,
                    "name": d.name or d.id,
                    "kwh": s["kwh"],
                    "cost_rp": s["cost_rp"],
                    "avg_power_w": s["avg_power_w"],
                    "peak_w": s["peak_w"],
                    "peak_time_wib": peak_hour_wib,
                    "cost_estimated": s["cost_estimated"],
                }
            )
        return {
            "range": range_arg or "custom",
            "from_wib": datetime.fromtimestamp(f_ts, tz=TZ_WIB).strftime("%d/%m/%Y %H:%M"),
            "to_wib": datetime.fromtimestamp(t_ts, tz=TZ_WIB).strftime("%d/%m/%Y %H:%M"),
            "devices": summaries,
            "total_kwh": round(sum(x["kwh"] for x in summaries), 3),
            "total_cost_rp": sum(x["cost_rp"] for x in summaries),
        }

    if tool_name == "compare_periods":
        a_from = int(args["a_from"])
        a_to = int(args["a_to"])
        b_from = int(args["b_from"])
        b_to = int(args["b_to"])
        _validate_bounds(a_from, a_to)
        _validate_bounds(b_from, b_to)

        a_kwh = 0.0
        a_rp = 0
        b_kwh = 0.0
        b_rp = 0
        hour_diff: dict[int, float] = {h: 0.0 for h in range(24)}
        for d in devs:
            sa = calculate_device_summary(session, d.id, from_ts=a_from, to_ts=a_to, now_dt=now_dt)
            sb = calculate_device_summary(session, d.id, from_ts=b_from, to_ts=b_to, now_dt=now_dt)
            a_kwh += sa["kwh"]
            a_rp += sa["cost_rp"]
            b_kwh += sb["kwh"]
            b_rp += sb["cost_rp"]

            rows_a = session.scalars(
                select(HourlyStat).where(
                    HourlyStat.device_id == d.id,
                    HourlyStat.hour_start >= a_from,
                    HourlyStat.hour_start <= a_to,
                )
            ).all()
            rows_b = session.scalars(
                select(HourlyStat).where(
                    HourlyStat.device_id == d.id,
                    HourlyStat.hour_start >= b_from,
                    HourlyStat.hour_start <= b_to,
                )
            ).all()
            for r in rows_a:
                h = datetime.fromtimestamp(r.hour_start, tz=TZ_WIB).hour
                hour_diff[h] += r.kwh
            for r in rows_b:
                h = datetime.fromtimestamp(r.hour_start, tz=TZ_WIB).hour
                hour_diff[h] -= r.kwh

        top_hour = max(hour_diff.items(), key=lambda kv: abs(kv[1]))
        diff_kwh = round(a_kwh - b_kwh, 3)
        diff_pct = round(((a_kwh - b_kwh) / b_kwh) * 100.0, 1) if b_kwh > 0 else None
        return {
            "period_a": {"kwh": round(a_kwh, 3), "cost_rp": a_rp},
            "period_b": {"kwh": round(b_kwh, 3), "cost_rp": b_rp},
            "diff_kwh": diff_kwh,
            "diff_cost_rp": a_rp - b_rp,
            "diff_percent": diff_pct,
            "top_contributing_hour_wib": f"{top_hour[0]:02d}:00",
            "top_hour_diff_kwh": round(top_hour[1], 3),
        }

    if tool_name == "get_hourly_profile":
        f_ts, t_ts = _resolve_range_bounds(args.get("range") or "today", now_dt=now_dt)
        _validate_bounds(f_ts, t_ts)
        dev_ids = [d.id for d in devs]
        rows = session.scalars(
            select(HourlyStat).where(
                HourlyStat.device_id.in_(dev_ids),
                HourlyStat.hour_start >= f_ts,
                HourlyStat.hour_start <= t_ts,
            )
        ).all()

        buckets: dict[int, list[float]] = {h: [] for h in range(24)}
        for r in rows:
            h = datetime.fromtimestamp(r.hour_start, tz=TZ_WIB).hour
            buckets[h].append(r.p_avg)
        if not rows:
            raw_rows = session.scalars(
                select(Reading).where(
                    Reading.device_id.in_(dev_ids),
                    Reading.ts >= f_ts,
                    Reading.ts <= t_ts,
                )
            ).all()
            for rr in raw_rows:
                h = datetime.fromtimestamp(rr.ts, tz=TZ_WIB).hour
                buckets[h].append(rr.p)

        profile = {
            f"{h:02d}": round(sum(vals) / len(vals), 1)
            for h, vals in buckets.items()
            if vals
        }
        peak_h = max(profile.items(), key=lambda kv: kv[1])[0] if profile else None
        return {
            "range": args.get("range") or "today",
            "avg_watt_by_hour_wib": profile,
            "peak_hour_wib": f"{peak_h}:00" if peak_h else None,
        }

    if tool_name == "get_anomalies":
        f_ts, t_ts = _resolve_range_bounds(args.get("range") or "this_week", now_dt=now_dt)
        _validate_bounds(f_ts, t_ts)
        dev_ids = [d.id for d in devs]
        anoms = session.scalars(
            select(Anomaly)
            .where(Anomaly.device_id.in_(dev_ids), Anomaly.ts >= f_ts, Anomaly.ts <= t_ts)
            .order_by(Anomaly.ts.desc())
            .limit(20)
        ).all()
        return {
            "count": len(anoms),
            "anomalies": [
                {
                    "device_id": a.device_id,
                    "time_wib": datetime.fromtimestamp(a.ts, tz=TZ_WIB).strftime("%d/%m %H:%M"),
                    "type": a.type,
                    "severity": a.severity,
                    "message": a.message,
                }
                for a in anoms
            ],
        }

    if tool_name == "get_forecast":
        forecasts = []
        for d in devs:
            fc = calculate_device_forecast(session, d.id, now_dt=now_dt)
            forecasts.append({"device_id": d.id, "name": d.name or d.id, **fc})
        return {"devices": forecasts}

    raise ValueError(f"Tool '{tool_name}' tidak dikenal.")


def cleanup_unused_ref() -> float:
    return time_mod.time()
