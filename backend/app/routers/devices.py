from datetime import datetime, time, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import DailyStat, Device, HourlyStat, Reading
from app.mqtt_ingest import get_device_status
from app.services.reports import calculate_device_forecast, calculate_device_summary

router = APIRouter(
    prefix="/api/devices", tags=["Devices"], dependencies=[Depends(get_current_user)]
)

TZ_WIB = ZoneInfo("Asia/Jakarta")


@router.get("", response_model=list[dict[str, Any]])
def list_devices(session: Session = Depends(get_db)):
    """Mengambil daftar perangkat terdaftar beserta status dinamis online/offline."""
    devices = session.scalars(select(Device).order_by(Device.id.asc())).all()
    now_utc = int(datetime.now(timezone.utc).timestamp())
    return [
        {
            "id": d.id,
            "name": d.name,
            "location": d.location,
            "mcb_watt": d.mcb_watt,
            "created_at": d.created_at,
            "last_seen_at": d.last_seen_at,
            "last_data_ts": d.last_data_ts,
            "status": get_device_status(d, now_utc=now_utc),
        }
        for d in devices
    ]


@router.get("/{device_id}/latest")
def get_latest_reading(device_id: str, session: Session = Depends(get_db)):
    """Mengambil data telemetri terbaru dari perangkat tertentu."""
    device = session.scalar(select(Device).where(Device.id == device_id))
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": 404, "message": f"Device '{device_id}' not found"}},
        )

    reading = session.scalar(
        select(Reading).where(Reading.device_id == device_id).order_by(Reading.ts.desc()).limit(1)
    )
    if not reading:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": 404,
                    "message": f"No telemetry readings found for device '{device_id}'",
                }
            },
        )

    return {
        "device_id": device_id,
        "ts": int(reading.ts),
        "v": reading.v,
        "i": reading.i,
        "p": reading.p,
        "e": reading.e_kwh,
        "delta_kwh": reading.delta_kwh,
        "f": reading.f,
        "pf": reading.pf,
        "rssi": reading.rssi,
        "is_gap": reading.is_gap,
    }


@router.get("/{device_id}/series")
def get_device_series(
    device_id: str,
    from_ts: Optional[int] = Query(None, alias="from"),
    to_ts: Optional[int] = Query(None, alias="to"),
    resolution: Optional[str] = Query("auto"),
    session: Session = Depends(get_db),
):
    """Mengambil deret waktu telemetri daya dengan pemilihan resolusi otomatis atau spesifik."""
    device = session.scalar(select(Device).where(Device.id == device_id))
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": 404, "message": f"Device '{device_id}' not found"}},
        )

    now_utc = int(datetime.now(timezone.utc).timestamp())
    end_time = to_ts if to_ts is not None else now_utc
    start_time = from_ts if from_ts is not None else (end_time - 86400)

    delta_sec = end_time - start_time
    if delta_sec < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {"code": 422, "message": "'from' timestamp must be <= 'to' timestamp"}
            },
        )
    if delta_sec > 366 * 86400:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": 422, "message": "Time range cannot exceed 366 days"}},
        )

    res = resolution
    if res == "auto":
        if delta_sec <= 5 * 3600:
            res = "raw"
        elif delta_sec <= 3 * 86400:
            res = "5m"
        elif delta_sec <= 60 * 86400:
            res = "1h"
        else:
            res = "1d"

    points: list[dict[str, Any]] = []
    interval_seconds = 10

    if res == "raw":
        interval_seconds = 10
        stmt = (
            select(Reading.ts, Reading.p, Reading.v)
            .where(
                Reading.device_id == device_id,
                Reading.ts >= start_time,
                Reading.ts <= end_time,
            )
            .order_by(Reading.ts.asc())
            .limit(2001)
        )
        rows = session.execute(stmt).all()
        for r in rows:
            points.append(
                {
                    "ts": int(r[0]),
                    "p": round(float(r[1]), 1),
                    "p_max": round(float(r[1]), 1),
                    "p_min": round(float(r[1]), 1),
                    "v": round(float(r[2]), 1),
                }
            )

    elif res == "5m":
        interval_seconds = 300
        bucket_expr = cast(Reading.ts / 300, Integer) * 300
        stmt = (
            select(
                bucket_expr.label("bucket_ts"),
                func.avg(Reading.p),
                func.max(Reading.p),
                func.min(Reading.p),
                func.avg(Reading.v),
            )
            .where(
                Reading.device_id == device_id,
                Reading.ts >= start_time,
                Reading.ts <= end_time,
            )
            .group_by("bucket_ts")
            .order_by("bucket_ts")
            .limit(2001)
        )
        rows = session.execute(stmt).all()
        for r in rows:
            points.append(
                {
                    "ts": int(r[0]),
                    "p": round(float(r[1]), 1),
                    "p_max": round(float(r[2]), 1),
                    "p_min": round(float(r[3]), 1),
                    "v": round(float(r[4]), 1),
                }
            )

    elif res == "1h":
        interval_seconds = 3600
        stmt = (
            select(
                HourlyStat.hour_start,
                HourlyStat.p_avg,
                HourlyStat.p_max,
                HourlyStat.p_min,
            )
            .where(
                HourlyStat.device_id == device_id,
                HourlyStat.hour_start >= start_time,
                HourlyStat.hour_start <= end_time,
            )
            .order_by(HourlyStat.hour_start.asc())
            .limit(2001)
        )
        rows = session.execute(stmt).all()
        for r in rows:
            points.append(
                {
                    "ts": int(r[0]),
                    "p": round(float(r[1]), 1),
                    "p_max": round(float(r[2]), 1),
                    "p_min": round(float(r[3]), 1),
                    "v": None,
                }
            )

    else:  # "1d"
        interval_seconds = 86400
        stmt = (
            select(DailyStat.day, DailyStat.kwh, DailyStat.p_max)
            .where(DailyStat.device_id == device_id)
            .order_by(DailyStat.day.asc())
            .limit(2001)
        )
        rows = session.execute(stmt).all()
        for r in rows:
            d_date = datetime.strptime(r[0], "%Y-%m-%d").date()
            d_epoch = int(datetime.combine(d_date, time(0, 0, 0), tzinfo=TZ_WIB).timestamp())
            if start_time <= d_epoch <= end_time:
                # Estimasi rata-rata watt harian = kWh * 1000 / 24 jam
                avg_watt = round((float(r[1]) * 1000.0) / 24.0, 1)
                points.append(
                    {
                        "ts": d_epoch,
                        "p": avg_watt,
                        "p_max": round(float(r[2]), 1),
                        "p_min": 0.0,
                        "v": None,
                    }
                )

    truncated = len(points) > 2000
    if truncated:
        points = points[:2000]

    return {
        "device_id": device_id,
        "from": start_time,
        "to": end_time,
        "interval_seconds": interval_seconds,
        "truncated": truncated,
        "points": points,
    }


@router.get("/{device_id}/summary")
def get_device_summary(
    device_id: str,
    range: Optional[str] = Query(None),
    from_ts: Optional[int] = Query(None, alias="from"),
    to_ts: Optional[int] = Query(None, alias="to"),
    session: Session = Depends(get_db),
):
    """Rangkuman konsumsi kWh, biaya, rata-rata, dan beban puncak untuk periode tertentu."""
    return calculate_device_summary(
        session=session,
        device_id=device_id,
        range=range,
        from_ts=from_ts,
        to_ts=to_ts,
    )


@router.get("/{device_id}/forecast")
def get_device_forecast(device_id: str, session: Session = Depends(get_db)):
    """Menghitung proyeksi kWh dan biaya akhir bulan kalender berjalan."""
    return calculate_device_forecast(session=session, device_id=device_id)
