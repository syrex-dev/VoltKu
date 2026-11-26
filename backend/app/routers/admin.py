import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_admin,
    get_trusted_client_ip,
    hash_password,
    login_limiter,
    verify_password,
)
from app.config import get_settings
from app.db import get_db
from app.models import (
    Anomaly,
    Device,
    PaymentMethod,
    Reading,
    Setting,
    TermsConsent,
    UpgradeRequest,
    User,
    UserSetting,
)
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
from app.routers.users import EMAIL_RE, _serialize_user, _validate_password_policy
from app.services.app_config import (
    get_active_terms_version,
    get_admin_app_settings,
    get_app_config_map,
    update_admin_app_settings,
)
from app.services.email_service import (
    is_smtp_configured,
    issue_password_reset_token,
    send_password_reset_email,
)
from app.services.payments import (
    ALLOWED_PAYMENT_TYPES,
    delete_private_image,
    expire_stale_awaiting_requests,
    resolve_private_image_path,
    save_private_image,
    serialize_payment_method,
)
from app.services.plans import (
    ACTIVE_UPGRADE_STATUSES,
    apply_user_plan_update,
    serialize_upgrade_request,
)

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
    plan_tier: str = "free"
    plan_duration_days: Optional[int] = None


class AdminUserUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None
    plan_tier: Optional[str] = None
    plan_duration_days: Optional[int] = None
    clear_plan_expiration: Optional[bool] = None


class AdminUpgradeResolveRequest(BaseModel):
    action: str  # "approve" | "reject"
    duration_days: Optional[int] = None
    admin_note: Optional[str] = None


class AdminPaymentMethodCreateRequest(BaseModel):
    type: str = "bank"  # qris | bank | ewallet
    label: str
    account_number: Optional[str] = None
    account_holder: Optional[str] = None
    instructions: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0
    qris_image_base64: Optional[str] = None


class AdminPaymentMethodUpdateRequest(BaseModel):
    type: Optional[str] = None
    label: Optional[str] = None
    account_number: Optional[str] = None
    account_holder: Optional[str] = None
    instructions: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
    qris_image_base64: Optional[str] = None


class AdminQrisUploadRequest(BaseModel):
    image_base64: str


class AdminDeviceUpdateRequest(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    mcb_watt: Optional[int] = None
    owner_user_id: Optional[int] = None
    is_public_demo: Optional[bool] = None


class AdminAppSettingsUpdateRequest(BaseModel):
    app_name: Optional[str] = None
    app_tagline: Optional[str] = None
    navbar_brand_display: Optional[str] = None
    announcement_active: Optional[bool] = None
    announcement_text: Optional[str] = None
    announcement_url: Optional[str] = None
    default_theme: Optional[str] = None
    onboarding_enabled: Optional[bool] = None
    onboarding_step1_title: Optional[str] = None
    onboarding_step1_desc: Optional[str] = None
    onboarding_step2_title: Optional[str] = None
    onboarding_step2_desc: Optional[str] = None
    onboarding_step3_title: Optional[str] = None
    onboarding_step3_desc: Optional[str] = None
    public_read_enabled: Optional[bool] = None
    registration_enabled: Optional[bool] = None
    google_auth_enabled: Optional[bool] = None
    google_client_id: Optional[str] = None
    google_android_client_id: Optional[str] = None
    require_terms_consent: Optional[bool] = None
    terms_version: Optional[str] = None
    privacy_version: Optional[str] = None
    legal_updated_at: Optional[str] = None
    terms_title: Optional[str] = None
    terms_content: Optional[str] = None
    privacy_title: Optional[str] = None
    privacy_content: Optional[str] = None
    support_whatsapp: Optional[str] = None
    support_telegram: Optional[str] = None
    support_email: Optional[str] = None
    freemium_enabled: Optional[bool] = None
    free_plan_name: Optional[str] = None
    free_max_devices: Optional[int] = None
    free_history_days: Optional[int] = None
    free_forecast_enabled: Optional[bool] = None
    free_export_enabled: Optional[bool] = None
    pro_plan_name: Optional[str] = None
    pro_monthly_price_rp: Optional[int] = None
    pro_yearly_price_rp: Optional[int] = None
    pro_max_devices: Optional[int] = None
    pro_history_days: Optional[int] = None
    upgrade_instructions: Optional[str] = None
    tariff_rp: Optional[str] = None
    power_limit_w: Optional[int] = None
    alert_cooldown_min: Optional[int] = None
    extra_percent: Optional[float] = None
    report_hour: Optional[int] = None
    report_enabled: Optional[bool] = None


def _admin_err(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"error": {"code": code, "message": message}})


@auth_router.post("/login", response_model=dict[str, str])
def admin_login(req: AdminLoginRequest, request: Request):
    """Endpoint login terpisah khusus Portal Admin (/admin) dengan rate limit per IP."""
    client_ip = get_trusted_client_ip(request)
    is_limited, retry_after = login_limiter.check_rate_limit(client_ip)
    if is_limited:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            content={
                "error": {"code": 429, "message": "Too many failed attempts. Retry later."}
            },
        )

    if not verify_password(req.password):
        delay = login_limiter.record_failure(client_ip)
        headers = {"Retry-After": str(delay)} if delay > 0 else {}
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers=headers,
            content={"error": {"code": 401, "message": "Kata sandi Admin salah"}},
        )

    login_limiter.record_success(client_ip)
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
    now_utc = int(time.time())
    users_pro = (
        session.scalar(
            select(func.count(User.id)).where(
                User.plan_tier == "pro",
                (User.plan_expires_at.is_(None)) | (User.plan_expires_at > now_utc),
            )
        )
        or 0
    )
    pending_upgrades = (
        session.scalar(
            select(func.count(UpgradeRequest.id)).where(
                UpgradeRequest.status.in_(ACTIVE_UPGRADE_STATUSES)
            )
        )
        or 0
    )

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
        "users_pro": int(users_pro),
        "pending_upgrades": int(pending_upgrades),
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
    """Daftar seluruh akun tenant/pembeli beserta jumlah perangkat dan paket langganannya."""
    users = session.scalars(select(User).order_by(User.id.desc())).all()
    cfg_map = get_app_config_map(session)
    dev_counts = dict(
        session.execute(
            select(Device.owner_user_id, func.count(Device.id))
            .where(Device.owner_user_id.is_not(None))
            .group_by(Device.owner_user_id)
        ).all()
    )
    results = []
    for u in users:
        cnt = int(dev_counts.get(u.id, 0))
        item = _serialize_user(u, session=session, cfg_map=cfg_map, device_count=cnt)
        item["device_count"] = cnt
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
    try:
        apply_user_plan_update(
            user,
            plan_tier=req.plan_tier,
            duration_days=req.plan_duration_days,
        )
    except ValueError as err:
        raise _admin_err(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err)) from err

    session.add(user)
    session.commit()
    session.refresh(user)
    cfg_map = get_app_config_map(session)
    item = _serialize_user(user, session=session, cfg_map=cfg_map, device_count=0)
    item["device_count"] = 0
    return item


@router.patch("/users/{user_id}", response_model=dict[str, Any])
def update_admin_user(
    user_id: int,
    req: AdminUserUpdateRequest,
    session: Session = Depends(get_db),
):
    """Mengubah nama, status aktif, sandi, atau paket langganan akun tenant."""
    user = session.get(User, user_id)
    if not user:
        raise _admin_err(status.HTTP_404_NOT_FOUND, "User not found")

    if req.name is not None:
        clean_name = req.name.strip()
        if len(clean_name) < 2 or len(clean_name) > 128:
            raise _admin_err(status.HTTP_422_UNPROCESSABLE_ENTITY, "Nama minimal 2 karakter")
        user.name = clean_name
    if req.email is not None:
        clean_email = req.email.strip().lower()
        if not EMAIL_RE.match(clean_email) or len(clean_email) > 128:
            raise _admin_err(status.HTTP_422_UNPROCESSABLE_ENTITY, "Format email tidak valid")
        conflict = session.scalar(
            select(User).where(User.email == clean_email, User.id != user.id)
        )
        if conflict:
            raise _admin_err(status.HTTP_409_CONFLICT, "Email sudah dipakai oleh akun lain")
        user.email = clean_email
    if req.is_active is not None:
        user.is_active = 1 if req.is_active else 0
    if req.password is not None and req.password.strip():
        _validate_password_policy(req.password)
        user.password_hash = hash_password(req.password)

    if (
        req.plan_tier is not None
        or req.plan_duration_days is not None
        or req.clear_plan_expiration
    ):
        try:
            apply_user_plan_update(
                user,
                plan_tier=req.plan_tier,
                duration_days=req.plan_duration_days,
                clear_expiration=bool(req.clear_plan_expiration),
            )
        except ValueError as err:
            raise _admin_err(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err)) from err

    session.commit()
    session.refresh(user)
    dev_count = int(
        session.scalar(select(func.count(Device.id)).where(Device.owner_user_id == user.id)) or 0
    )
    cfg_map = get_app_config_map(session)
    item = _serialize_user(user, session=session, cfg_map=cfg_map, device_count=dev_count)
    item["device_count"] = dev_count
    return item


@router.post("/users/{user_id}/send-reset-link", response_model=dict[str, Any])
def admin_send_user_reset_link(
    user_id: int,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
):
    """Memicu pengiriman tautan reset kata sandi ke email pembeli langsung dari Panel Admin."""
    user = session.get(User, user_id)
    if not user:
        raise _admin_err(status.HTTP_404_NOT_FOUND, "Akun pengguna tidak ditemukan")
    if not user.is_active:
        raise _admin_err(
            status.HTTP_409_CONFLICT,
            "Aktifkan akun terlebih dahulu sebelum mengirim tautan reset kata sandi.",
        )

    raw_token = issue_password_reset_token(session, user.id)
    smtp_ready = is_smtp_configured()
    background_tasks.add_task(
        send_password_reset_email,
        to_email=user.email,
        user_name=user.name,
        raw_token=raw_token,
        expires_minutes=30,
    )
    return {
        "sent": True,
        "smtp_configured": smtp_ready,
        "email": user.email,
        "message": (
            f"Tautan reset kata sandi dikirim ke {user.email}."
            if smtp_ready
            else f"Token reset dibuat untuk {user.email}, namun SMTP_HOST di server belum diatur."
        ),
    }


@router.delete("/users/{user_id}", response_model=dict[str, Any])
def delete_admin_user(user_id: int, session: Session = Depends(get_db)):
    """Menghapus tenant user dan melepas kepemilikan perangkatnya (tanpa hapus histori)."""
    user = session.get(User, user_id)
    if not user:
        raise _admin_err(status.HTTP_404_NOT_FOUND, "User not found")

    owned = session.scalars(select(Device).where(Device.owner_user_id == user_id)).all()
    for dev in owned:
        dev.owner_user_id = None
    consents = session.scalars(select(TermsConsent).where(TermsConsent.user_id == user_id)).all()
    for c in consents:
        c.user_id = None
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


@router.get("/app-settings", response_model=dict[str, Any])
def get_admin_application_settings(session: Session = Depends(get_db)):
    """Membaca seluruh pengaturan aplikasi (brand, panduan, legal, auth, operasional)."""
    return get_admin_app_settings(session)


@router.patch("/app-settings", response_model=dict[str, Any])
def update_admin_application_settings(
    req: AdminAppSettingsUpdateRequest,
    session: Session = Depends(get_db),
):
    """Memperbarui pengaturan aplikasi terpusat dari Panel Admin."""
    payload = req.model_dump(exclude_unset=True)
    try:
        return update_admin_app_settings(session, payload)
    except ValueError as err:
        raise _admin_err(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err)) from err


@router.get("/consents", response_model=dict[str, Any])
def get_admin_terms_consents(
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_db),
):
    """Audit riwayat persetujuan Syarat Penggunaan & Kebijakan Privasi pengguna dan tamu."""
    current_ver = get_active_terms_version(session)
    rows = session.scalars(
        select(TermsConsent)
        .order_by(TermsConsent.accepted_at.desc(), TermsConsent.id.desc())
        .limit(limit)
    ).all()
    users = session.scalars(select(User)).all()
    users_map = {u.id: u for u in users}

    agreed_current = sum(1 for u in users if u.terms_version_accepted == current_ver)
    pending_or_outdated = len(users) - agreed_current

    items = []
    for r in rows:
        usr = users_map.get(r.user_id) if r.user_id is not None else None
        items.append(
            {
                "id": r.id,
                "user_id": r.user_id,
                "user_name": usr.name if usr else None,
                "email": usr.email if usr else r.email_snapshot,
                "client_id": r.client_id,
                "terms_version": r.terms_version,
                "privacy_version": r.privacy_version,
                "accepted_via": r.accepted_via,
                "ip_address": r.ip_address,
                "user_agent": r.user_agent,
                "accepted_at": r.accepted_at,
                "is_current_version": r.terms_version == current_ver,
            }
        )

    return {
        "current_terms_version": current_ver,
        "users_total": len(users),
        "users_agreed_current": agreed_current,
        "users_pending_or_outdated": pending_or_outdated,
        "total_logged": len(items),
        "items": items,
    }


@router.get("/upgrade-requests", response_model=list[dict[str, Any]])
def list_admin_upgrade_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_db),
):
    """Daftar pengajuan upgrade paket & bukti bayar untuk ditinjau Admin."""
    expire_stale_awaiting_requests(session)
    session.commit()
    stmt = select(UpgradeRequest)
    if status_filter:
        clean_filter = status_filter.strip().lower()
        if clean_filter == "active":
            stmt = stmt.where(UpgradeRequest.status.in_(ACTIVE_UPGRADE_STATUSES))
        elif clean_filter in (
            "pending",
            "awaiting_payment",
            "verifying",
            "approved",
            "rejected",
            "cancelled",
            "expired",
        ):
            stmt = stmt.where(UpgradeRequest.status == clean_filter)
    rows = session.scalars(
        stmt.order_by(UpgradeRequest.created_at.desc(), UpgradeRequest.id.desc()).limit(limit)
    ).all()
    users_map = {u.id: u for u in session.scalars(select(User)).all()}
    return [serialize_upgrade_request(r, user=users_map.get(r.user_id)) for r in rows]


@router.patch("/upgrade-requests/{request_id}", response_model=dict[str, Any])
def resolve_admin_upgrade_request(
    request_id: int,
    req: AdminUpgradeResolveRequest,
    session: Session = Depends(get_db),
):
    """Menyetujui atau menolak pengajuan upgrade user sekaligus mengaktifkan paket Pro."""
    entry = session.get(UpgradeRequest, request_id)
    if not entry:
        raise _admin_err(status.HTTP_404_NOT_FOUND, "Permintaan upgrade tidak ditemukan")
    if entry.status not in ACTIVE_UPGRADE_STATUSES:
        raise _admin_err(
            status.HTTP_409_CONFLICT,
            f"Permintaan ini sudah berstatus '{entry.status}'",
        )

    action = (req.action or "").strip().lower()
    if action not in ("approve", "reject"):
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "action harus 'approve' atau 'reject'",
        )

    user = session.get(User, entry.user_id)
    if not user:
        raise _admin_err(status.HTTP_404_NOT_FOUND, "Akun pengguna tidak ditemukan")

    now_utc = int(time.time())
    clean_note = req.admin_note.strip()[:255] if req.admin_note and req.admin_note.strip() else None

    if action == "approve":
        default_days = 365 if entry.billing_cycle == "yearly" else 30
        days_to_apply = default_days if req.duration_days is None else int(req.duration_days)
        apply_user_plan_update(
            user,
            plan_tier=entry.requested_tier or "pro",
            duration_days=days_to_apply,
        )
        entry.status = "approved"
    else:
        entry.status = "rejected"

    entry.admin_note = clean_note
    entry.resolved_at = now_utc
    session.commit()
    session.refresh(entry)
    return serialize_upgrade_request(entry, user=user)


@router.get("/upgrade-requests/{request_id}/proof")
def get_admin_upgrade_proof_image(
    request_id: int,
    session: Session = Depends(get_db),
):
    """Mengunduh foto bukti pembayaran milik tagihan tertentu untuk diperiksa Admin."""
    entry = session.get(UpgradeRequest, request_id)
    if not entry:
        raise _admin_err(status.HTTP_404_NOT_FOUND, "Tagihan upgrade tidak ditemukan")
    resolved = resolve_private_image_path(entry.payment_proof_path)
    if not resolved:
        raise _admin_err(status.HTTP_404_NOT_FOUND, "Bukti pembayaran belum diunggah")
    file_path, media_type = resolved
    return FileResponse(
        file_path,
        media_type=media_type,
        headers={"Cache-Control": "private, no-store"},
    )


@router.get("/payment-methods", response_model=list[dict[str, Any]])
def list_admin_payment_methods(session: Session = Depends(get_db)):
    """Daftar seluruh metode pembayaran manual (aktif & nonaktif) di Panel Admin."""
    rows = session.scalars(
        select(PaymentMethod).order_by(PaymentMethod.sort_order.asc(), PaymentMethod.id.asc())
    ).all()
    return [serialize_payment_method(r) for r in rows]


@router.post("/payment-methods", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def create_admin_payment_method(
    req: AdminPaymentMethodCreateRequest,
    session: Session = Depends(get_db),
):
    """Menambah metode pembayaran manual baru (QRIS, Bank, atau E-Wallet)."""
    pm_type = (req.type or "bank").strip().lower()
    if pm_type not in ALLOWED_PAYMENT_TYPES:
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Tipe metode pembayaran harus 'qris', 'bank', atau 'ewallet'.",
        )
    clean_label = req.label.strip()
    if len(clean_label) < 2 or len(clean_label) > 64:
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Nama metode pembayaran harus antara 2 hingga 64 karakter.",
        )

    qris_rel: Optional[str] = None
    if req.qris_image_base64 and req.qris_image_base64.strip():
        try:
            qris_rel = save_private_image("qris", req.qris_image_base64)
        except ValueError as err:
            raise _admin_err(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err)) from err

    pm = PaymentMethod(
        type=pm_type,
        label=clean_label,
        account_number=(req.account_number or "").strip()[:64] or None,
        account_holder=(req.account_holder or "").strip()[:128] or None,
        instructions=(req.instructions or "").strip() or None,
        qris_image_path=qris_rel,
        is_active=1 if req.is_active else 0,
        sort_order=int(req.sort_order or 0),
        created_at=int(time.time()),
    )
    session.add(pm)
    session.commit()
    session.refresh(pm)
    return serialize_payment_method(pm)


@router.patch("/payment-methods/{method_id}", response_model=dict[str, Any])
def update_admin_payment_method(
    method_id: int,
    req: AdminPaymentMethodUpdateRequest,
    session: Session = Depends(get_db),
):
    """Memperbarui detail, status aktif, atau gambar QRIS metode pembayaran manual."""
    pm = session.get(PaymentMethod, method_id)
    if not pm:
        raise _admin_err(status.HTTP_404_NOT_FOUND, "Metode pembayaran tidak ditemukan")

    if req.type is not None:
        pm_type = req.type.strip().lower()
        if pm_type not in ALLOWED_PAYMENT_TYPES:
            raise _admin_err(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Tipe metode pembayaran harus 'qris', 'bank', atau 'ewallet'.",
            )
        pm.type = pm_type
    if req.label is not None:
        clean_label = req.label.strip()
        if len(clean_label) < 2 or len(clean_label) > 64:
            raise _admin_err(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Nama metode pembayaran harus antara 2 hingga 64 karakter.",
            )
        pm.label = clean_label
    if req.account_number is not None:
        pm.account_number = req.account_number.strip()[:64] or None
    if req.account_holder is not None:
        pm.account_holder = req.account_holder.strip()[:128] or None
    if req.instructions is not None:
        pm.instructions = req.instructions.strip() or None
    if req.is_active is not None:
        pm.is_active = 1 if req.is_active else 0
    if req.sort_order is not None:
        pm.sort_order = int(req.sort_order)
    if req.qris_image_base64 is not None and req.qris_image_base64.strip():
        try:
            new_qris = save_private_image("qris", req.qris_image_base64)
        except ValueError as err:
            raise _admin_err(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err)) from err
        old_qris = pm.qris_image_path
        pm.qris_image_path = new_qris
        pm.created_at = int(time.time())
        if old_qris and old_qris != new_qris:
            delete_private_image(old_qris)

    session.commit()
    session.refresh(pm)
    return serialize_payment_method(pm)


@router.post("/payment-methods/{method_id}/qris", response_model=dict[str, Any])
def upload_admin_payment_method_qris(
    method_id: int,
    req: AdminQrisUploadRequest,
    session: Session = Depends(get_db),
):
    """Mengunggah atau mengganti gambar QRIS untuk metode pembayaran manual."""
    pm = session.get(PaymentMethod, method_id)
    if not pm:
        raise _admin_err(status.HTTP_404_NOT_FOUND, "Metode pembayaran tidak ditemukan")
    try:
        new_qris = save_private_image("qris", req.image_base64)
    except ValueError as err:
        raise _admin_err(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err)) from err
    old_qris = pm.qris_image_path
    pm.qris_image_path = new_qris
    pm.created_at = int(time.time())
    session.commit()
    session.refresh(pm)
    if old_qris and old_qris != new_qris:
        delete_private_image(old_qris)
    return serialize_payment_method(pm)


@router.delete("/payment-methods/{method_id}", response_model=dict[str, Any])
def delete_admin_payment_method(
    method_id: int,
    session: Session = Depends(get_db),
):
    """Menghapus metode pembayaran manual."""
    pm = session.get(PaymentMethod, method_id)
    if not pm:
        raise _admin_err(status.HTTP_404_NOT_FOUND, "Metode pembayaran tidak ditemukan")
    old_qris = pm.qris_image_path
    session.delete(pm)
    session.commit()
    if old_qris:
        delete_private_image(old_qris)
    return {"deleted": True, "id": method_id}
