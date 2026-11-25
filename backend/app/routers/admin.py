import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_admin,
    hash_password,
    login_limiter,
    verify_password,
)
from app.config import get_settings
from app.db import get_db
from app.models import Anomaly, Device, Reading, Setting, User, UserSetting
from app.mqtt_ingest import ingest_service
from app.routers.anomalies import query_anomalies_list
from app.routers.devices import (
    _normalize_location,
    _serialize_device,
    _validate_mcb_watt,
    list_devices_data,
)
from app.routers.public import PUBLIC_ACCESS_KEY, is_public_dashboard_enabled
from app.routers.settings import format_settings_response, get_all_settings
from app.routers.users import EMAIL_RE, _serialize_user

auth_router = APIRouter(prefix="/api/admin", tags=["Admin Auth"])
router = APIRouter(
    prefix="/api/admin", tags=["Admin"], dependencies=[Depends(get_current_admin)]
)


class AdminLoginRequest(BaseModel):
    password: str


class AccessPolicyRequest(BaseModel):
    public_read_enabled: bool


class AdminUserCreateRequest(BaseModel):
    name: str
    email: str
    password: str


class AdminUserUpdateRequest(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None


class AdminDeviceUpdateRequest(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    mcb_watt: Optional[int] = None
    owner_user_id: Optional[int] = None
    is_public_demo: Optional[bool] = None


def _admin_err(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"error": {"code": code, "message": message}})


@auth_router.post("/login", response_model=dict[str, str])
def admin_login(req: AdminLoginRequest, response: Response):
    """Endpoint login terpisah khusus Portal Admin (/admin)."""
    is_limited, retry_after = login_limiter.check_rate_limit()
    if is_limited:
        response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
        response.headers["Retry-After"] = str(retry_after)
        return Response(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            content='{"error":{"code":429,"message":"Too many failed attempts. Retry later."}}',
            media_type="application/json",
        )

    if not verify_password(req.password):
        delay = login_limiter.record_failure()
        headers = {"Retry-After": str(delay)} if delay > 0 else {}
        return Response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers=headers,
            content='{"error":{"code":401,"message":"Kata sandi Admin salah"}}',
            media_type="application/json",
        )

    login_limiter.record_success()
    token = create_access_token(subject="dashboard_admin", role="admin")
    return {"token": token, "token_type": "bearer"}


@router.get("/overview", response_model=dict[str, Any])
def get_admin_overview(session: Session = Depends(get_db)):
    """Ringkasan kesehatan sistem, perangkat, tenant user, dan layanan untuk Panel Admin."""
    devices = list_devices_data(session, include_latest=False)
    online_count = sum(1 for d in devices if d.get("status") == "online")
    offline_count = len(devices) - online_count
    claimed_count = sum(1 for d in devices if d.get("owner_user_id") is not None)
    demo_count = sum(1 for d in devices if d.get("is_public_demo"))

    users_total = session.scalar(select(func.count(User.id))) or 0
    users_active = session.scalar(select(func.count(User.id)).where(User.is_active == 1)) or 0

    cutoff_7d = int(time.time()) - (7 * 86400)
    anomalies_7d = session.scalar(
        select(func.count(Anomaly.id)).where(Anomaly.ts >= cutoff_7d)
    ) or 0
    readings_total = session.scalar(select(func.count(Reading.id))) or 0

    cfg = get_settings()
    sys_settings = format_settings_response(get_all_settings(session))

    mqtt_client = getattr(ingest_service, "_mqtt_client", None)
    mqtt_connected = bool(mqtt_client and mqtt_client.is_connected())
    worker_thread = getattr(ingest_service, "_worker_thread", None)
    worker_alive = bool(worker_thread and worker_thread.is_alive())

    return {
        "devices_total": len(devices),
        "devices_online": online_count,
        "devices_offline": offline_count,
        "devices_claimed": claimed_count,
        "devices_unclaimed": len(devices) - claimed_count,
        "devices_public_demo": demo_count,
        "users_total": int(users_total),
        "users_active": int(users_active),
        "anomalies_7d": int(anomalies_7d),
        "readings_total": int(readings_total),
        "public_read_enabled": is_public_dashboard_enabled(session),
        "tariff_rp": sys_settings["tariff_rp"],
        "power_limit_w": sys_settings["power_limit_w"],
        "mqtt_connected": mqtt_connected,
        "ingest_worker_alive": worker_alive,
        "ingest_queue_size": int(ingest_service.queue.qsize()),
        "scheduler_enabled": bool(cfg.is_scheduler_active),
        "bot_configured": bool(cfg.is_bot_active),
    }


@router.get("/users", response_model=list[dict[str, Any]])
def list_admin_users(session: Session = Depends(get_db)):
    """Daftar seluruh akun tenant/pembeli beserta jumlah perangkat miliknya."""
    users = session.scalars(select(User).order_by(User.id.desc())).all()
    dev_counts = dict(
        session.execute(
            select(Device.owner_user_id, func.count(Device.id))
            .where(Device.owner_user_id.is_not(None))
            .group_by(Device.owner_user_id)
        ).all()
    )
    results = []
    for u in users:
        item = _serialize_user(u)
        item["device_count"] = int(dev_counts.get(u.id, 0))
        results.append(item)
    return results


@router.post("/users", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def create_admin_user(req: AdminUserCreateRequest, session: Session = Depends(get_db)):
    """Membuat akun pembeli baru dari Panel Admin."""
    clean_name = req.name.strip()
    clean_email = req.email.strip().lower()
    if len(clean_name) < 2 or len(clean_name) > 128:
        raise _admin_err(status.HTTP_422_UNPROCESSABLE_ENTITY, "Nama minimal 2 karakter")
    if not EMAIL_RE.match(clean_email):
        raise _admin_err(status.HTTP_422_UNPROCESSABLE_ENTITY, "Format email tidak valid")
    if len(req.password) < 6:
        raise _admin_err(status.HTTP_422_UNPROCESSABLE_ENTITY, "Kata sandi minimal 6 karakter")

    existing = session.scalar(select(User).where(User.email == clean_email))
    if existing:
        raise _admin_err(status.HTTP_409_CONFLICT, "Email sudah digunakan")

    user = User(
        name=clean_name,
        email=clean_email,
        password_hash=hash_password(req.password),
        is_active=1,
        created_at=int(datetime.now(timezone.utc).timestamp()),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    item = _serialize_user(user)
    item["device_count"] = 0
    return item


@router.patch("/users/{user_id}", response_model=dict[str, Any])
def update_admin_user(
    user_id: int,
    req: AdminUserUpdateRequest,
    session: Session = Depends(get_db),
):
    """Mengubah nama, status aktif, atau reset sandi akun tenant."""
    user = session.get(User, user_id)
    if not user:
        raise _admin_err(status.HTTP_404_NOT_FOUND, "User not found")

    if req.name is not None:
        clean_name = req.name.strip()
        if len(clean_name) < 2 or len(clean_name) > 128:
            raise _admin_err(status.HTTP_422_UNPROCESSABLE_ENTITY, "Nama minimal 2 karakter")
        user.name = clean_name
    if req.is_active is not None:
        user.is_active = 1 if req.is_active else 0
    if req.password is not None and req.password.strip():
        if len(req.password) < 6:
            raise _admin_err(status.HTTP_422_UNPROCESSABLE_ENTITY, "Kata sandi minimal 6 karakter")
        user.password_hash = hash_password(req.password)

    session.commit()
    session.refresh(user)
    dev_count = (
        session.scalar(select(func.count(Device.id)).where(Device.owner_user_id == user.id)) or 0
    )
    item = _serialize_user(user)
    item["device_count"] = int(dev_count)
    return item


@router.delete("/users/{user_id}", response_model=dict[str, Any])
def delete_admin_user(user_id: int, session: Session = Depends(get_db)):
    """Menghapus tenant user dan melepas kepemilikan perangkatnya (tanpa hapus histori)."""
    user = session.get(User, user_id)
    if not user:
        raise _admin_err(status.HTTP_404_NOT_FOUND, "User not found")

    owned = session.scalars(select(Device).where(Device.owner_user_id == user_id)).all()
    for dev in owned:
        dev.owner_user_id = None
    session.execute(delete(UserSetting).where(UserSetting.user_id == user_id))
    session.delete(user)
    session.commit()
    return {"deleted": True, "id": user_id}


@router.get("/devices", response_model=list[dict[str, Any]])
def get_admin_devices(session: Session = Depends(get_db)):
    """Daftar lengkap unit perangkat beserta pemilik tenant, metrik, & status Demo Publik."""
    devices = list_devices_data(session, include_latest=True)
    cutoff_7d = int(time.time()) - (7 * 86400)

    users_map = {u.id: u for u in session.scalars(select(User)).all()}
    reading_counts = dict(
        session.execute(
            select(Reading.device_id, func.count(Reading.id)).group_by(Reading.device_id)
        ).all()
    )
    anomaly_counts = dict(
        session.execute(
            select(Anomaly.device_id, func.count(Anomaly.id))
            .where(Anomaly.ts >= cutoff_7d)
            .group_by(Anomaly.device_id)
        ).all()
    )

    for d in devices:
        dev_id = d["id"]
        uid = d.get("owner_user_id")
        owner = users_map.get(uid) if uid is not None else None
        d["owner_name"] = owner.name if owner else None
        d["owner_email"] = owner.email if owner else None
        d["readings_count"] = int(reading_counts.get(dev_id, 0))
        d["anomalies_7d"] = int(anomaly_counts.get(dev_id, 0))
    return devices


@router.patch("/devices/{device_id}", response_model=dict[str, Any])
def update_admin_device(
    device_id: str,
    req: AdminDeviceUpdateRequest,
    session: Session = Depends(get_db),
):
    """Pembaruan administratif: metadata, pengalihan pemilik tenant, & flag Demo Publik."""
    device = session.scalar(select(Device).where(Device.id == device_id))
    if not device:
        raise _admin_err(status.HTTP_404_NOT_FOUND, f"Device '{device_id}' not found")

    if req.name is not None:
        clean_name = req.name.strip()
        if not clean_name or len(clean_name) > 128:
            raise _admin_err(status.HTTP_422_UNPROCESSABLE_ENTITY, "Nama perangkat tidak valid")
        device.name = clean_name
    if req.location is not None:
        device.location = _normalize_location(req.location)
    if req.mcb_watt is not None:
        device.mcb_watt = _validate_mcb_watt(req.mcb_watt)
    if req.is_public_demo is not None:
        device.is_public_demo = 1 if req.is_public_demo else 0
    if req.owner_user_id is not None:
        if req.owner_user_id <= 0:
            device.owner_user_id = None
        else:
            owner = session.get(User, req.owner_user_id)
            if not owner:
                raise _admin_err(status.HTTP_404_NOT_FOUND, "Akun pemilik tidak ditemukan")
            device.owner_user_id = owner.id

    session.commit()
    session.refresh(device)
    return _serialize_device(device)


@router.get("/anomalies", response_model=list[dict[str, Any]])
def get_admin_anomalies(
    device_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    from_ts: Optional[int] = Query(None, alias="from"),
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_db),
):
    """Log anomali terpusat lintas semua perangkat untuk audit admin."""
    return query_anomalies_list(
        session=session,
        device_id=device_id,
        from_ts=from_ts,
        severity=severity,
        limit=limit,
    )


@router.get("/access", response_model=dict[str, bool])
def get_admin_access_policy(session: Session = Depends(get_db)):
    """Mengambil status toggle mode akses unit demo tanpa login."""
    return {"public_read_enabled": is_public_dashboard_enabled(session)}


@router.patch("/access", response_model=dict[str, bool])
def update_admin_access_policy(
    req: AccessPolicyRequest,
    session: Session = Depends(get_db),
):
    """Mengaktifkan atau menonaktifkan mode pantau demo publik tanpa login."""
    val_str = "true" if req.public_read_enabled else "false"
    row = session.scalar(select(Setting).where(Setting.key == PUBLIC_ACCESS_KEY))
    if not row:
        session.add(Setting(key=PUBLIC_ACCESS_KEY, value=val_str))
    else:
        row.value = val_str
    session.commit()
    return {"public_read_enabled": req.public_read_enabled}
