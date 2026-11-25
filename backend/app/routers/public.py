from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Device, Setting
from app.routers.anomalies import query_anomalies_list
from app.routers.devices import (
    get_device_series_data,
    get_latest_reading_data,
    list_devices_data,
)
from app.routers.settings import format_settings_response, get_all_settings
from app.services.reports import calculate_device_forecast, calculate_device_summary

PUBLIC_ACCESS_KEY = "public_dashboard_enabled"

router = APIRouter(prefix="/api/public", tags=["Public"])


def is_public_dashboard_enabled(session: Session) -> bool:
    """Mengembalikan True jika mode baca Tanpa Login diaktifkan."""
    row = session.scalar(select(Setting).where(Setting.key == PUBLIC_ACCESS_KEY))
    if row is not None:
        return row.value.strip().lower() in ("true", "1", "yes", "on")
    return bool(get_settings().public_dashboard_enabled)


def require_public_read(session: Session = Depends(get_db)) -> None:
    """Memblokir akses baca publik dengan HTTP 401 jika admin menutup mode Tanpa Login."""
    if not is_public_dashboard_enabled(session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": 401, "message": "Public dashboard access is disabled"}},
            headers={"WWW-Authenticate": "Bearer"},
        )


def _ensure_public_demo_device(session: Session, device_id: str) -> Device:
    """Pastikan pengunjung Tanpa Login hanya bisa mengakses perangkat bertanda Demo Publik."""
    device = session.scalar(
        select(Device).where(Device.id == device_id, Device.is_public_demo == 1)
    )
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": 404, "message": f"Device '{device_id}' not found"}},
        )
    return device


@router.get("/access", response_model=dict[str, bool])
def get_public_access_status(session: Session = Depends(get_db)):
    """Status apakah pengunjung dapat memantau unit demo tanpa login."""
    return {"public_read_enabled": is_public_dashboard_enabled(session)}


@router.get(
    "/devices",
    response_model=list[dict[str, Any]],
    dependencies=[Depends(require_public_read)],
)
def public_list_devices(
    include_latest: bool = Query(False),
    session: Session = Depends(get_db),
):
    """Daftar perangkat Demo Publik (read-only) untuk pengunjung tanpa login."""
    return list_devices_data(session, include_latest=include_latest, public_demo_only=True)


@router.get(
    "/devices/{device_id}/latest",
    dependencies=[Depends(require_public_read)],
)
def public_latest_reading(device_id: str, session: Session = Depends(get_db)):
    """Pembacaan telemetri terbaru perangkat Demo Publik."""
    _ensure_public_demo_device(session, device_id)
    return get_latest_reading_data(session, device_id)


@router.get(
    "/devices/{device_id}/series",
    dependencies=[Depends(require_public_read)],
)
def public_device_series(
    device_id: str,
    from_ts: Optional[int] = Query(None, alias="from"),
    to_ts: Optional[int] = Query(None, alias="to"),
    resolution: Optional[str] = Query("auto"),
    session: Session = Depends(get_db),
):
    """Deret waktu daya perangkat Demo Publik."""
    _ensure_public_demo_device(session, device_id)
    return get_device_series_data(
        session=session,
        device_id=device_id,
        from_ts=from_ts,
        to_ts=to_ts,
        resolution=resolution,
    )


@router.get(
    "/devices/{device_id}/summary",
    dependencies=[Depends(require_public_read)],
)
def public_device_summary(
    device_id: str,
    range: Optional[str] = Query(None),
    from_ts: Optional[int] = Query(None, alias="from"),
    to_ts: Optional[int] = Query(None, alias="to"),
    session: Session = Depends(get_db),
):
    """Rangkuman kWh & estimasi tagihan perangkat Demo Publik."""
    _ensure_public_demo_device(session, device_id)
    return calculate_device_summary(
        session=session,
        device_id=device_id,
        range=range,
        from_ts=from_ts,
        to_ts=to_ts,
    )


@router.get(
    "/devices/{device_id}/forecast",
    dependencies=[Depends(require_public_read)],
)
def public_device_forecast(device_id: str, session: Session = Depends(get_db)):
    """Proyeksi akhir bulan perangkat Demo Publik."""
    _ensure_public_demo_device(session, device_id)
    return calculate_device_forecast(session=session, device_id=device_id)


@router.get(
    "/anomalies",
    response_model=list[dict[str, Any]],
    dependencies=[Depends(require_public_read)],
)
def public_anomalies(
    device_id: Optional[str] = Query(None),
    from_ts: Optional[int] = Query(None, alias="from"),
    session: Session = Depends(get_db),
):
    """Daftar anomali terbaru khusus perangkat Demo Publik."""
    return query_anomalies_list(
        session=session,
        device_id=device_id,
        from_ts=from_ts,
        public_demo_only=True,
    )


@router.get(
    "/settings",
    dependencies=[Depends(require_public_read)],
)
def public_settings(session: Session = Depends(get_db)):
    """Konfigurasi tarif dasar non-rahasia (read-only) untuk tampilan demo publik."""
    return format_settings_response(get_all_settings(session))
