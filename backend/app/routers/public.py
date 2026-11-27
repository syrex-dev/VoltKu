from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_trusted_client_ip, public_consent_limiter
from app.config import get_settings
from app.db import get_db
from app.models import Device, PaymentMethod, Setting
from app.routers.anomalies import query_anomalies_list
from app.routers.devices import (
    build_device_daily_csv_response,
    get_device_series_data,
    get_latest_reading_data,
    list_devices_data,
)
from app.routers.settings import format_settings_response, get_all_settings
from app.services.app_config import get_app_config_map, get_public_app_config, record_terms_consent
from app.services.payments import resolve_private_image_path, serialize_payment_method
from app.services.plans import build_public_plans_payload
from app.services.reports import calculate_device_forecast, calculate_device_summary
from app.services.sync_state import compute_public_sync_state

PUBLIC_ACCESS_KEY = "public_dashboard_enabled"

router = APIRouter(prefix="/api/public", tags=["Public"])
payment_router = APIRouter(prefix="/api/payment-methods", tags=["Payments"])


class PublicTermsConsentRequest(BaseModel):
    accepted: bool
    client_id: str
    terms_version: Optional[str] = None


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


@router.get("/sync-state", response_model=dict[str, Any])
def get_public_sync_state(session: Session = Depends(get_db)):
    """Fingerprint ringan untuk sinkronisasi otomatis perubahan admin ke halaman publik."""
    return compute_public_sync_state(session)


@router.get("/app-config", response_model=dict[str, Any])
def get_public_app_configuration(session: Session = Depends(get_db)):
    """Konfigurasi aplikasi publik (brand, panduan, auth/Google, teks legal, kontak dukungan)."""
    return get_public_app_config(session)


@router.get("/plans", response_model=dict[str, Any])
def get_public_subscription_plans(session: Session = Depends(get_db)):
    """Daftar seluruh paket langganan aktif beserta harga promo & fitur."""
    return build_public_plans_payload(get_app_config_map(session), session=session)


@router.get("/payment-methods", response_model=list[dict[str, Any]])
def list_public_payment_methods(session: Session = Depends(get_db)):
    """Daftar metode pembayaran manual aktif (QRIS, Bank, E-Wallet) untuk checkout Pro."""
    rows = session.scalars(
        select(PaymentMethod)
        .where(PaymentMethod.is_active == 1)
        .order_by(PaymentMethod.sort_order.asc(), PaymentMethod.id.asc())
    ).all()
    return [serialize_payment_method(r) for r in rows]


@payment_router.get("/{method_id}/qris")
def get_payment_method_qris_image(method_id: int, session: Session = Depends(get_db)):
    """Menyajikan gambar QRIS dari direktori privat untuk metode pembayaran terkait."""
    pm = session.get(PaymentMethod, method_id)
    if not pm or not pm.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": 404, "message": "Metode pembayaran tidak ditemukan"}},
        )
    resolved = resolve_private_image_path(pm.qris_image_path)
    if not resolved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": 404, "message": "Gambar QRIS belum tersedia"}},
        )
    file_path, media_type = resolved
    return FileResponse(
        file_path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.post("/terms-consent", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def record_public_terms_consent(
    req: PublicTermsConsentRequest,
    request: Request,
    session: Session = Depends(get_db),
):
    """Mencatat persetujuan Syarat Penggunaan & Privasi dari pengguna/perangkat sebelum login."""
    client_ip = get_trusted_client_ip(request)
    is_limited, retry_after = public_consent_limiter.check_and_record(client_ip)
    if is_limited:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            content={
                "error": {
                    "code": 429,
                    "message": "Terlalu banyak permintaan persetujuan. Coba lagi nanti.",
                }
            },
        )

    if not req.accepted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": 422,
                    "message": "Persetujuan harus bernilai true untuk dicatat.",
                }
            },
        )
    clean_client = req.client_id.strip()
    if len(clean_client) < 4 or len(clean_client) > 128:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {"code": 422, "message": "client_id harus antara 4 dan 128 karakter."}
            },
        )

    entry = record_terms_consent(
        session,
        user=None,
        email_snapshot=None,
        client_id=clean_client,
        accepted_via="guest",
        accepted_terms_version=req.terms_version,
        request=request,
    )
    session.commit()
    return {
        "recorded": True,
        "id": entry.id,
        "terms_version": entry.terms_version,
        "privacy_version": entry.privacy_version,
        "accepted_at": entry.accepted_at,
    }


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
    "/devices/{device_id}/export",
    dependencies=[Depends(require_public_read)],
)
def public_device_export_csv(
    device_id: str,
    days: int = Query(30, ge=1, le=30),
    session: Session = Depends(get_db),
):
    """Ekspor laporan harian CSV perangkat Demo Publik (read-only)."""
    _ensure_public_demo_device(session, device_id)
    return build_device_daily_csv_response(session=session, device_id=device_id, days=days)


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
