import csv
import io
import re
from datetime import datetime, time, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.constants import OFFLINE_THRESHOLD_SECONDS
from app.db import get_db
from app.models import AlertState, Anomaly, DailyStat, Device, HourlyStat, Reading
from app.mqtt_ingest import get_device_status
from app.services.app_config import get_app_config_map
from app.services.plans import (
    enforce_device_creation_quota,
    enforce_series_history_access,
    enforce_user_feature_access,
)
from app.services.reports import calculate_device_forecast, calculate_device_summary

router = APIRouter(
    prefix="/api/devices", tags=["Devices"], dependencies=[Depends(get_current_user)]
)

TZ_WIB = ZoneInfo("Asia/Jakarta")
DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{2,64}$")


class DeviceCreateRequest(BaseModel):
    id: str
    name: str
    location: Optional[str] = None
    mcb_watt: int = 2200
    claim: bool = False


class DeviceUpdateRequest(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    mcb_watt: Optional[int] = None


def _raise_api_error(status_code: int, message: str) -> None:
    raise HTTPException(
        status_code=status_code,
        detail={"error": {"code": status_code, "message": message}},
    )


def _validate_mcb_watt(mcb_watt: int) -> int:
    if not (100 <= mcb_watt <= 25000):
        _raise_api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "mcb_watt must be between 100 and 25000",
        )
    return mcb_watt


def _normalize_location(location: Optional[str]) -> Optional[str]:
    if location is None:
        return None
    cleaned = location.strip()
    if len(cleaned) > 128:
        _raise_api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "location must not exceed 128 characters",
        )
    return cleaned or None


def _serialize_reading(reading: Reading) -> dict[str, Any]:
    return {
        "device_id": reading.device_id,
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


def _serialize_device(
    device: Device,
    now_utc: Optional[int] = None,
    latest: Optional[Reading] = None,
    include_latest: bool = False,
) -> dict[str, Any]:
    if now_utc is None:
        now_utc = int(datetime.now(timezone.utc).timestamp())
    data: dict[str, Any] = {
        "id": device.id,
        "name": device.name,
        "location": device.location,
        "mcb_watt": device.mcb_watt,
        "owner_user_id": device.owner_user_id,
        "is_public_demo": bool(device.is_public_demo),
        "created_at": device.created_at,
        "last_seen_at": device.last_seen_at,
        "last_data_ts": device.last_data_ts,
        "status": get_device_status(
            device, now_utc=now_utc, threshold_seconds=OFFLINE_THRESHOLD_SECONDS
        ),
    }
    if include_latest:
        data["latest"] = _serialize_reading(latest) if latest else None
    return data


def _get_device_for_actor(
    session: Session, device_id: str, current: dict[str, Any]
) -> Device:
    """Memastikan perangkat ada dan dimiliki oleh actor bila role='user'."""
    device = session.scalar(select(Device).where(Device.id == device_id))
    if not device:
        _raise_api_error(status.HTTP_404_NOT_FOUND, f"Device '{device_id}' not found")
    if current.get("role") == "user" and device.owner_user_id != current.get("user_id"):
        _raise_api_error(
            status.HTTP_403_FORBIDDEN,
            "Anda tidak memiliki akses ke perangkat ini",
        )
    return device


def list_devices_data(
    session: Session,
    include_latest: bool = False,
    owner_user_id: Optional[int] = None,
    public_demo_only: bool = False,
) -> list[dict[str, Any]]:
    """Query helper daftar perangkat dengan filter kepemilikan / mode demo publik."""
    stmt = select(Device)
    if public_demo_only:
        stmt = stmt.where(Device.is_public_demo == 1)
    elif owner_user_id is not None:
        stmt = stmt.where(Device.owner_user_id == owner_user_id)
    devices = session.scalars(stmt.order_by(Device.id.asc())).all()
    now_utc = int(datetime.now(timezone.utc).timestamp())

    latest_by_device: dict[str, Reading] = {}
    if include_latest and devices:
        dev_ids = [d.id for d in devices]
        subq = (
            select(Reading.device_id, func.max(Reading.ts).label("max_ts"))
            .where(Reading.device_id.in_(dev_ids))
            .group_by(Reading.device_id)
            .subquery()
        )
        rows = session.scalars(
            select(Reading).join(
                subq,
                (Reading.device_id == subq.c.device_id) & (Reading.ts == subq.c.max_ts),
            )
        ).all()
        latest_by_device = {r.device_id: r for r in rows}

    return [
        _serialize_device(
            d,
            now_utc=now_utc,
            latest=latest_by_device.get(d.id),
            include_latest=include_latest,
        )
        for d in devices
    ]


@router.get("", response_model=list[dict[str, Any]])
def list_devices(
    include_latest: bool = Query(False),
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Mengambil daftar perangkat terdaftar (terisolasi per user bila role=user)."""
    uid = current.get("user_id") if current.get("role") == "user" else None
    return list_devices_data(session, include_latest=include_latest, owner_user_id=uid)


@router.post("", response_model=dict[str, Any])
def create_or_claim_device(
    req: DeviceCreateRequest,
    response: Response,
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Mendaftarkan perangkat baru atau mengklaim perangkat tak bertuan."""
    dev_id = req.id.strip()
    if not DEVICE_ID_RE.match(dev_id):
        _raise_api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "id must be 2-64 characters using letters, numbers, '-' or '_'",
        )

    clean_name = req.name.strip()
    if not clean_name or len(clean_name) > 128:
        _raise_api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "name must be between 1 and 128 characters",
        )

    clean_loc = _normalize_location(req.location)
    mcb_watt = _validate_mcb_watt(req.mcb_watt)
    actor_uid = current.get("user_id") if current.get("role") == "user" else None

    existing = session.scalar(select(Device).where(Device.id == dev_id))
    now_utc = int(datetime.now(timezone.utc).timestamp())

    if existing:
        if (
            actor_uid is not None
            and existing.owner_user_id is not None
            and existing.owner_user_id != actor_uid
        ):
            _raise_api_error(
                status.HTTP_409_CONFLICT,
                "Perangkat ini sudah diklaim oleh akun lain",
            )
        if not req.claim:
            _raise_api_error(
                status.HTTP_409_CONFLICT,
                f"Device '{dev_id}' already exists",
            )
        if actor_uid is not None and existing.owner_user_id is None:
            enforce_device_creation_quota(session, int(actor_uid), get_app_config_map(session))
        existing.name = clean_name
        existing.location = clean_loc
        existing.mcb_watt = mcb_watt
        if actor_uid is not None:
            existing.owner_user_id = actor_uid
        session.commit()
        session.refresh(existing)
        response.status_code = status.HTTP_200_OK
        return _serialize_device(existing, now_utc=now_utc)

    if actor_uid is not None:
        enforce_device_creation_quota(session, int(actor_uid), get_app_config_map(session))

    device = Device(
        id=dev_id,
        name=clean_name,
        location=clean_loc,
        mcb_watt=mcb_watt,
        owner_user_id=actor_uid,
        is_public_demo=0,
        created_at=now_utc,
        status="offline",
    )
    session.add(device)
    session.commit()
    session.refresh(device)
    response.status_code = status.HTTP_201_CREATED
    return _serialize_device(device, now_utc=now_utc)


@router.patch("/{device_id}", response_model=dict[str, Any])
def update_device(
    device_id: str,
    req: DeviceUpdateRequest,
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Memperbarui nama, ruangan/lokasi, atau batas MCB perangkat milik sendiri/admin."""
    device = _get_device_for_actor(session, device_id, current)

    if req.name is not None:
        clean_name = req.name.strip()
        if not clean_name or len(clean_name) > 128:
            _raise_api_error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "name must be between 1 and 128 characters",
            )
        device.name = clean_name

    if req.location is not None:
        device.location = _normalize_location(req.location)

    if req.mcb_watt is not None:
        device.mcb_watt = _validate_mcb_watt(req.mcb_watt)

    session.commit()
    session.refresh(device)
    return _serialize_device(device)


@router.delete("/{device_id}", response_model=dict[str, Any])
def delete_device(
    device_id: str,
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Menghapus perangkat beserta seluruh data telemetri dan anomali terkait."""
    device = _get_device_for_actor(session, device_id, current)

    for model in (Reading, HourlyStat, DailyStat, Anomaly, AlertState):
        session.execute(delete(model).where(model.device_id == device_id))
    session.delete(device)
    session.commit()
    return {"deleted": True, "id": device_id}


def get_latest_reading_data(session: Session, device_id: str) -> dict[str, Any]:
    """Helper pembacaan telemetri terbaru perangkat."""
    device = session.scalar(select(Device).where(Device.id == device_id))
    if not device:
        _raise_api_error(status.HTTP_404_NOT_FOUND, f"Device '{device_id}' not found")

    reading = session.scalar(
        select(Reading).where(Reading.device_id == device_id).order_by(Reading.ts.desc()).limit(1)
    )
    if not reading:
        _raise_api_error(
            status.HTTP_404_NOT_FOUND,
            f"No telemetry readings found for device '{device_id}'",
        )

    return _serialize_reading(reading)


@router.get("/{device_id}/latest")
def get_latest_reading(
    device_id: str,
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Mengambil data telemetri terbaru dari perangkat tertentu."""
    _get_device_for_actor(session, device_id, current)
    return get_latest_reading_data(session, device_id)


def get_device_series_data(
    session: Session,
    device_id: str,
    from_ts: Optional[int] = None,
    to_ts: Optional[int] = None,
    resolution: Optional[str] = "auto",
) -> dict[str, Any]:
    """Helper deret waktu telemetri daya dengan resolusi otomatis atau spesifik."""
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
        bucket_expr = Reading.ts - (Reading.ts % 300)
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


@router.get("/{device_id}/series")
def get_device_series(
    device_id: str,
    from_ts: Optional[int] = Query(None, alias="from"),
    to_ts: Optional[int] = Query(None, alias="to"),
    resolution: Optional[str] = Query("auto"),
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Mengambil deret waktu telemetri daya dengan pemilihan resolusi otomatis atau spesifik."""
    _get_device_for_actor(session, device_id, current)
    now_utc = int(datetime.now(timezone.utc).timestamp())
    end_time = to_ts if to_ts is not None else now_utc
    start_time = from_ts if from_ts is not None else (end_time - 86400)
    enforce_series_history_access(
        session, current, start_time, end_time, get_app_config_map(session)
    )
    return get_device_series_data(
        session=session,
        device_id=device_id,
        from_ts=from_ts,
        to_ts=to_ts,
        resolution=resolution,
    )


@router.get("/{device_id}/summary")
def get_device_summary(
    device_id: str,
    range: Optional[str] = Query(None),
    from_ts: Optional[int] = Query(None, alias="from"),
    to_ts: Optional[int] = Query(None, alias="to"),
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Rangkuman konsumsi kWh, biaya, rata-rata, dan beban puncak untuk periode tertentu."""
    _get_device_for_actor(session, device_id, current)
    return calculate_device_summary(
        session=session,
        device_id=device_id,
        range=range,
        from_ts=from_ts,
        to_ts=to_ts,
    )


@router.get("/{device_id}/forecast")
def get_device_forecast(
    device_id: str,
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Menghitung proyeksi kWh dan biaya akhir bulan kalender berjalan."""
    _get_device_for_actor(session, device_id, current)
    enforce_user_feature_access(
        session,
        current,
        "forecast_enabled",
        "forecast",
        "Proyeksi tagihan akhir bulan tersedia pada paket VoltKu Pro.",
        get_app_config_map(session),
    )
    return calculate_device_forecast(session=session, device_id=device_id)


@router.get("/{device_id}/export")
def export_device_daily_csv(
    device_id: str,
    days: int = Query(30, ge=1, le=366),
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Ekspor laporan konsumsi harian perangkat ke CSV (khusus paket Pro/admin)."""
    _get_device_for_actor(session, device_id, current)
    enforce_user_feature_access(
        session,
        current,
        "export_enabled",
        "export_csv",
        "Ekspor laporan CSV tersedia pada paket VoltKu Pro.",
        get_app_config_map(session),
    )

    today_wib = datetime.now(TZ_WIB).date()
    start_day = (today_wib - timedelta(days=days - 1)).isoformat()
    rows = session.scalars(
        select(DailyStat)
        .where(DailyStat.device_id == device_id, DailyStat.day >= start_day)
        .order_by(DailyStat.day.desc())
    ).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["tanggal_wib", "energi_kwh", "biaya_rp", "tarif_rp_per_kwh", "daya_puncak_w"]
    )
    for r in rows:
        day_cell = str(r.day)
        if day_cell[:1] in ("=", "+", "-", "@", "\t", "\r"):
            day_cell = f"'{day_cell}"
        tariff_rp = f"{(int(r.tariff_sen) / 100):.2f}"
        writer.writerow(
            [
                day_cell,
                f"{float(r.kwh):.3f}",
                int(r.cost_rp),
                tariff_rp,
                round(float(r.p_max), 1),
            ]
        )

    buf.seek(0)
    filename = f"voltku-{device_id}-{days}d.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
