import json
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
    DiscountCode,
    PaymentMethod,
    Reading,
    Setting,
    SubscriptionPlan,
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
    delete_admin_visual_asset,
    get_active_terms_version,
    get_admin_app_settings,
    get_app_config_map,
    update_admin_app_settings,
    update_admin_visual_asset,
    upsert_app_config,
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
    ALLOWED_DISCOUNT_TYPES,
    DISCOUNT_CODE_RE,
    PLAN_SLUG_RE,
    apply_user_plan_update,
    ensure_default_plans_seeded,
    release_discount_usage,
    serialize_discount_code,
    serialize_plan,
    serialize_upgrade_request,
)
from app.services.sync_state import compute_admin_sync_state

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


class AdminPlanCreateRequest(BaseModel):
    slug: str
    name: str
    description: Optional[str] = None
    badge_text: Optional[str] = None
    price_monthly_rp: int = 0
    price_yearly_rp: int = 0
    promo_discount_type: Optional[str] = None
    promo_discount_value: int = 0
    promo_label: Optional[str] = None
    promo_starts_at: Optional[int] = None
    promo_expires_at: Optional[int] = None
    max_devices: int = 10
    history_days: int = 90
    forecast_enabled: bool = True
    export_enabled: bool = True
    anomaly_advanced: bool = True
    features: Optional[list[str]] = None
    is_recommended: bool = False
    is_active: bool = True
    sort_order: int = 10


class AdminPlanUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    badge_text: Optional[str] = None
    price_monthly_rp: Optional[int] = None
    price_yearly_rp: Optional[int] = None
    promo_discount_type: Optional[str] = None
    promo_discount_value: Optional[int] = None
    promo_label: Optional[str] = None
    promo_starts_at: Optional[int] = None
    promo_expires_at: Optional[int] = None
    max_devices: Optional[int] = None
    history_days: Optional[int] = None
    forecast_enabled: Optional[bool] = None
    export_enabled: Optional[bool] = None
    anomaly_advanced: Optional[bool] = None
    features: Optional[list[str]] = None
    is_recommended: Optional[bool] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class AdminDiscountCreateRequest(BaseModel):
    code: str
    label: Optional[str] = None
    discount_type: str = "percent"  # percent | fixed_rp
    discount_value: int = 10
    max_discount_rp: Optional[int] = None
    min_purchase_rp: int = 0
    target_plan_slug: Optional[str] = None
    target_cycle: Optional[str] = None
    max_uses: Optional[int] = None
    starts_at: Optional[int] = None
    expires_at: Optional[int] = None
    is_active: bool = True


class AdminDiscountUpdateRequest(BaseModel):
    code: Optional[str] = None
    label: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[int] = None
    max_discount_rp: Optional[int] = None
    min_purchase_rp: Optional[int] = None
    target_plan_slug: Optional[str] = None
    target_cycle: Optional[str] = None
    max_uses: Optional[int] = None
    starts_at: Optional[int] = None
    expires_at: Optional[int] = None
    is_active: Optional[bool] = None


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
    report_timezone: Optional[str] = None
    report_enabled: Optional[bool] = None
    hero_banners: Optional[list[dict[str, Any]]] = None


class AdminVisualAssetUpdateRequest(BaseModel):
    image_base64: Optional[str] = None
    enabled: Optional[bool] = None


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


@router.get("/sync-state", response_model=dict[str, Any])
def get_admin_sync_state(session: Session = Depends(get_db)):
    """Status sinkronisasi & jumlah antrean real-time untuk auto-refresh Panel Admin."""
    return compute_admin_sync_state(session)


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
                User.plan_tier != "free",
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
        "smtp_configured": bool(cfg.smtp_host and cfg.smtp_host.strip()),
    }


@router.get("/users", response_model=list[dict[str, Any]])
def list_admin_users(
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db),
):
    """Daftar akun tenant/pembeli beserta jumlah perangkat & paket (mendukung paginasi)."""
    users = session.scalars(
        select(User).order_by(User.id.desc()).offset(offset).limit(limit)
    ).all()
    cfg_map = get_app_config_map(session)
    user_ids = [u.id for u in users]
    dev_counts = (
        dict(
            session.execute(
                select(Device.owner_user_id, func.count(Device.id))
                .where(Device.owner_user_id.in_(user_ids))
                .group_by(Device.owner_user_id)
            ).all()
        )
        if user_ids
        else {}
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
            session=session,
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
                session=session,
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
def get_admin_devices(
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db),
):
    """Daftar unit perangkat beserta pemilik tenant, metrik, & status Demo Publik (paginasi)."""
    devices = list_devices_data(session, include_latest=True, limit=limit, offset=offset)
    cutoff_7d = int(time.time()) - (7 * 86400)

    owner_ids = {int(d["owner_user_id"]) for d in devices if d.get("owner_user_id") is not None}
    users_map = (
        {
            u.id: u
            for u in session.scalars(select(User).where(User.id.in_(owner_ids))).all()
        }
        if owner_ids
        else {}
    )
    dev_ids = [d["id"] for d in devices]
    reading_counts = (
        dict(
            session.execute(
                select(Reading.device_id, func.count(Reading.id))
                .where(Reading.device_id.in_(dev_ids))
                .group_by(Reading.device_id)
            ).all()
        )
        if dev_ids
        else {}
    )
    anomaly_counts = (
        dict(
            session.execute(
                select(Anomaly.device_id, func.count(Anomaly.id))
                .where(Anomaly.device_id.in_(dev_ids), Anomaly.ts >= cutoff_7d)
                .group_by(Anomaly.device_id)
            ).all()
        )
        if dev_ids
        else {}
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


@router.put("/visual-assets/{slot}", response_model=dict[str, Any])
def upsert_admin_visual_asset(
    slot: str,
    req: AdminVisualAssetUpdateRequest,
    session: Session = Depends(get_db),
):
    """Mengunggah/mengganti gambar kustom atau mengubah status tampil suatu slot aset visual."""
    try:
        return update_admin_visual_asset(
            session,
            slot,
            image_base64=req.image_base64,
            enabled=req.enabled,
        )
    except LookupError as err:
        raise _admin_err(status.HTTP_404_NOT_FOUND, str(err)) from err
    except ValueError as err:
        raise _admin_err(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err)) from err


@router.delete("/visual-assets/{slot}", response_model=dict[str, Any])
def remove_admin_visual_asset(
    slot: str,
    action: str = Query("reset", pattern="^(reset|disable)$"),
    session: Session = Depends(get_db),
):
    """Menghapus gambar custom (reset ke maskot bawaan atau disable dari tampilan aplikasi)."""
    try:
        return delete_admin_visual_asset(session, slot, action=action)
    except LookupError as err:
        raise _admin_err(status.HTTP_404_NOT_FOUND, str(err)) from err
    except ValueError as err:
        raise _admin_err(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err)) from err


@router.get("/consents", response_model=dict[str, Any])
def get_admin_terms_consents(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db),
):
    """Audit riwayat persetujuan Syarat Penggunaan & Kebijakan Privasi pengguna dan tamu."""
    current_ver = get_active_terms_version(session)
    rows = session.scalars(
        select(TermsConsent)
        .order_by(TermsConsent.accepted_at.desc(), TermsConsent.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    users_total = session.scalar(select(func.count(User.id))) or 0
    agreed_current = (
        session.scalar(
            select(func.count(User.id)).where(User.terms_version_accepted == current_ver)
        )
        or 0
    )
    pending_or_outdated = max(0, int(users_total) - int(agreed_current))

    consent_uids = {int(r.user_id) for r in rows if r.user_id is not None}
    users_map = (
        {
            u.id: u
            for u in session.scalars(select(User).where(User.id.in_(consent_uids))).all()
        }
        if consent_uids
        else {}
    )

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
        "users_total": int(users_total),
        "users_agreed_current": int(agreed_current),
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
    req_uids = {int(r.user_id) for r in rows}
    users_map = (
        {
            u.id: u
            for u in session.scalars(select(User).where(User.id.in_(req_uids))).all()
        }
        if req_uids
        else {}
    )
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
            session=session,
        )
        entry.status = "approved"
    else:
        entry.status = "rejected"
        release_discount_usage(session, entry)

    entry.admin_note = clean_note
    entry.resolved_at = now_utc
    session.commit()
    session.refresh(entry)

    try:
        from app.services.push_notifier import create_and_dispatch_user_notification

        tier_label = (
            entry.plan_name_snapshot or (entry.requested_tier or "pro").upper()
        )
        if action == "approve":
            order_label = entry.order_code or ""
            create_and_dispatch_user_notification(
                session,
                user_id=entry.user_id,
                title=f"{tier_label} Aktif!",
                body=(
                    f"Pembayaran {order_label} telah disetujui. "
                    f"Nikmati fitur penuh paket {tier_label}."
                ),
                category="billing",
                severity="success",
                data={
                    "upgrade_request_id": entry.id,
                    "order_code": order_label,
                    "action": "approved",
                },
                event_key=f"upgrade:{entry.id}:approved",
                now_ts=now_utc,
            )
        else:
            order_label = entry.order_code or ""
            reason_suffix = f" Catatan: {clean_note}" if clean_note else ""
            create_and_dispatch_user_notification(
                session,
                user_id=entry.user_id,
                title="Pembayaran Upgrade Ditolak",
                body=f"Pengajuan {order_label} tidak dapat diproses.{reason_suffix}",
                category="billing",
                severity="warning",
                data={
                    "upgrade_request_id": entry.id,
                    "order_code": order_label,
                    "action": "rejected",
                },
                event_key=f"upgrade:{entry.id}:rejected",
                now_ts=now_utc,
            )
    except Exception:
        pass

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


def _normalize_promo_and_limits(
    *,
    name: str,
    price_monthly_rp: int,
    price_yearly_rp: int,
    max_devices: int,
    history_days: int,
    promo_discount_type: Optional[str],
    promo_discount_value: int,
    promo_starts_at: Optional[int],
    promo_expires_at: Optional[int],
    is_default_free: bool = False,
) -> dict[str, Any]:
    clean_name = (name or "").strip()
    if len(clean_name) < 2 or len(clean_name) > 64:
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Nama paket harus antara 2 hingga 64 karakter.",
        )

    monthly_rp = 0 if is_default_free else int(price_monthly_rp or 0)
    yearly_rp = 0 if is_default_free else int(price_yearly_rp or 0)
    if monthly_rp < 0 or monthly_rp > 100_000_000:
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Harga bulanan harus antara Rp 0 hingga Rp 100.000.000.",
        )
    if yearly_rp < 0 or yearly_rp > 1_000_000_000:
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Harga tahunan harus antara Rp 0 hingga Rp 1.000.000.000.",
        )

    max_dev = int(max_devices)
    if max_dev == 0 or max_dev < -1 or max_dev > 10000:
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Kuota panel harus -1 (tanpa batas) atau antara 1 hingga 10000.",
        )
    hist_days = int(history_days)
    if hist_days < 1 or hist_days > 366:
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Riwayat hari grafik harus antara 1 hingga 366 hari.",
        )

    ptype = (promo_discount_type or "").strip().lower() or None
    pval = int(promo_discount_value or 0)
    if ptype is None or pval <= 0:
        ptype = None
        pval = 0
    elif ptype not in ALLOWED_DISCOUNT_TYPES:
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Tipe promo paket harus 'percent' atau 'fixed_rp'.",
        )
    elif ptype == "percent" and pval > 100:
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Diskon promo persen maksimal 100%.",
        )
    elif ptype == "fixed_rp" and pval > 100_000_000:
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Diskon nominal maksimal Rp 100.000.000.",
        )

    p_start = int(promo_starts_at) if promo_starts_at else None
    p_end = int(promo_expires_at) if promo_expires_at else None
    if p_start is not None and p_end is not None and p_end <= p_start:
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Waktu berakhir promo harus lebih besar dari waktu mulai.",
        )

    return {
        "name": clean_name,
        "price_monthly_rp": monthly_rp,
        "price_yearly_rp": yearly_rp,
        "max_devices": max_dev,
        "history_days": hist_days,
        "promo_discount_type": ptype,
        "promo_discount_value": pval,
        "promo_starts_at": p_start,
        "promo_expires_at": p_end,
    }


def _sync_plan_row_to_legacy_config(session: Session, plan: SubscriptionPlan) -> None:
    if plan.slug == "free" or plan.is_default_free:
        upsert_app_config(session, "free_plan_name", plan.name)
        upsert_app_config(session, "free_max_devices", str(max(1, int(plan.max_devices))))
        upsert_app_config(session, "free_history_days", str(int(plan.history_days)))
        upsert_app_config(
            session, "free_forecast_enabled", "true" if plan.forecast_enabled else "false"
        )
        upsert_app_config(
            session, "free_export_enabled", "true" if plan.export_enabled else "false"
        )
    elif plan.slug == "pro":
        upsert_app_config(session, "pro_plan_name", plan.name)
        upsert_app_config(session, "pro_monthly_price_rp", str(int(plan.price_monthly_rp)))
        upsert_app_config(session, "pro_yearly_price_rp", str(int(plan.price_yearly_rp)))
        upsert_app_config(session, "pro_max_devices", str(int(plan.max_devices)))
        upsert_app_config(session, "pro_history_days", str(int(plan.history_days)))


@router.get("/plans", response_model=list[dict[str, Any]])
def list_admin_plans(session: Session = Depends(get_db)):
    """Daftar seluruh paket langganan (aktif & nonaktif) beserta ringkasan promo."""
    cfg_map = get_app_config_map(session)
    rows = ensure_default_plans_seeded(session, cfg_map)
    session.commit()
    now_utc = int(time.time())
    user_counts = dict(
        session.execute(
            select(User.plan_tier, func.count(User.id)).group_by(User.plan_tier)
        ).all()
    )
    items = []
    for p in rows:
        data = serialize_plan(p, now_utc=now_utc)
        data["subscriber_count"] = int(user_counts.get(p.slug, 0))
        items.append(data)
    return items


@router.post("/plans", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def create_admin_plan(req: AdminPlanCreateRequest, session: Session = Depends(get_db)):
    """Menambah paket langganan baru lengkap dengan kuota fitur & promo harga coret."""
    cfg_map = get_app_config_map(session)
    ensure_default_plans_seeded(session, cfg_map)

    clean_slug = (req.slug or "").strip().lower()
    if not PLAN_SLUG_RE.match(clean_slug):
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Slug paket harus 2-32 huruf kecil/angka/'-'/'_' (diawali huruf/angka).",
        )
    if session.scalar(select(SubscriptionPlan).where(SubscriptionPlan.slug == clean_slug)):
        raise _admin_err(
            status.HTTP_409_CONFLICT,
            f"Kode slug paket '{clean_slug}' sudah dipakai.",
        )

    v = _normalize_promo_and_limits(
        name=req.name,
        price_monthly_rp=req.price_monthly_rp,
        price_yearly_rp=req.price_yearly_rp,
        max_devices=req.max_devices,
        history_days=req.history_days,
        promo_discount_type=req.promo_discount_type,
        promo_discount_value=req.promo_discount_value,
        promo_starts_at=req.promo_starts_at,
        promo_expires_at=req.promo_expires_at,
        is_default_free=False,
    )
    now_utc = int(time.time())
    clean_features = (
        [str(x).strip()[:120] for x in req.features if str(x).strip()]
        if req.features is not None
        else None
    )
    plan = SubscriptionPlan(
        slug=clean_slug,
        name=v["name"],
        description=(req.description or "").strip()[:255] or None,
        badge_text=(req.badge_text or "").strip()[:32] or None,
        price_monthly_rp=v["price_monthly_rp"],
        price_yearly_rp=v["price_yearly_rp"],
        promo_discount_type=v["promo_discount_type"],
        promo_discount_value=v["promo_discount_value"],
        promo_label=(req.promo_label or "").strip()[:48] or None,
        promo_starts_at=v["promo_starts_at"],
        promo_expires_at=v["promo_expires_at"],
        max_devices=v["max_devices"],
        history_days=v["history_days"],
        forecast_enabled=1 if req.forecast_enabled else 0,
        export_enabled=1 if req.export_enabled else 0,
        anomaly_advanced=1 if req.anomaly_advanced else 0,
        features_json=json.dumps(clean_features) if clean_features else None,
        is_default_free=0,
        is_recommended=1 if req.is_recommended else 0,
        is_active=1 if req.is_active else 0,
        sort_order=int(req.sort_order or 10),
        created_at=now_utc,
        updated_at=now_utc,
    )
    session.add(plan)
    session.commit()
    session.refresh(plan)
    data = serialize_plan(plan, now_utc=now_utc)
    data["subscriber_count"] = 0
    return data


@router.patch("/plans/{plan_id}", response_model=dict[str, Any])
def update_admin_plan(
    plan_id: int,
    req: AdminPlanUpdateRequest,
    session: Session = Depends(get_db),
):
    """Memperbarui detail harga, kuota fitur, promo harga coret, atau status paket."""
    cfg_map = get_app_config_map(session)
    ensure_default_plans_seeded(session, cfg_map)
    plan = session.get(SubscriptionPlan, plan_id)
    if not plan:
        raise _admin_err(status.HTTP_404_NOT_FOUND, "Paket langganan tidak ditemukan.")

    if plan.is_default_free and req.is_active is False:
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Paket gratis bawaan wajib tetap aktif sebagai dasar akun baru.",
        )

    v = _normalize_promo_and_limits(
        name=req.name if req.name is not None else plan.name,
        price_monthly_rp=(
            req.price_monthly_rp if req.price_monthly_rp is not None else plan.price_monthly_rp
        ),
        price_yearly_rp=(
            req.price_yearly_rp if req.price_yearly_rp is not None else plan.price_yearly_rp
        ),
        max_devices=req.max_devices if req.max_devices is not None else plan.max_devices,
        history_days=req.history_days if req.history_days is not None else plan.history_days,
        promo_discount_type=(
            req.promo_discount_type
            if "promo_discount_type" in req.model_fields_set
            else plan.promo_discount_type
        ),
        promo_discount_value=(
            req.promo_discount_value
            if req.promo_discount_value is not None
            else plan.promo_discount_value
        ),
        promo_starts_at=(
            req.promo_starts_at
            if "promo_starts_at" in req.model_fields_set
            else plan.promo_starts_at
        ),
        promo_expires_at=(
            req.promo_expires_at
            if "promo_expires_at" in req.model_fields_set
            else plan.promo_expires_at
        ),
        is_default_free=bool(plan.is_default_free),
    )

    plan.name = v["name"]
    plan.price_monthly_rp = v["price_monthly_rp"]
    plan.price_yearly_rp = v["price_yearly_rp"]
    plan.max_devices = v["max_devices"]
    plan.history_days = v["history_days"]
    plan.promo_discount_type = v["promo_discount_type"]
    plan.promo_discount_value = v["promo_discount_value"]
    plan.promo_starts_at = v["promo_starts_at"]
    plan.promo_expires_at = v["promo_expires_at"]

    if req.description is not None:
        plan.description = req.description.strip()[:255] or None
    if req.badge_text is not None:
        plan.badge_text = req.badge_text.strip()[:32] or None
    if req.promo_label is not None:
        plan.promo_label = req.promo_label.strip()[:48] or None
    if req.forecast_enabled is not None:
        plan.forecast_enabled = 1 if req.forecast_enabled else 0
    if req.export_enabled is not None:
        plan.export_enabled = 1 if req.export_enabled else 0
    if req.anomaly_advanced is not None:
        plan.anomaly_advanced = 1 if req.anomaly_advanced else 0
    if req.features is not None:
        clean_features = [str(x).strip()[:120] for x in req.features if str(x).strip()]
        plan.features_json = json.dumps(clean_features) if clean_features else None
    if req.is_recommended is not None:
        plan.is_recommended = 1 if req.is_recommended else 0
    if req.is_active is not None:
        plan.is_active = 1 if req.is_active else 0
    if req.sort_order is not None:
        plan.sort_order = int(req.sort_order)

    now_utc = int(time.time())
    plan.updated_at = now_utc
    _sync_plan_row_to_legacy_config(session, plan)
    session.commit()
    session.refresh(plan)
    sub_count = int(
        session.scalar(
            select(func.count(User.id)).where(User.plan_tier == plan.slug)
        )
        or 0
    )
    data = serialize_plan(plan, now_utc=now_utc)
    data["subscriber_count"] = sub_count
    return data


@router.delete("/plans/{plan_id}", response_model=dict[str, Any])
def delete_admin_plan(plan_id: int, session: Session = Depends(get_db)):
    """Menghapus paket kustom (paket gratis bawaan dan paket yang masih dipakai user dilindungi)."""
    plan = session.get(SubscriptionPlan, plan_id)
    if not plan:
        raise _admin_err(status.HTTP_404_NOT_FOUND, "Paket langganan tidak ditemukan.")
    if plan.is_default_free or plan.slug == "free":
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Paket gratis bawaan tidak boleh dihapus.",
        )

    active_users = int(
        session.scalar(
            select(func.count(User.id)).where(
                (User.plan_id == plan.id) | (User.plan_tier == plan.slug)
            )
        )
        or 0
    )
    if active_users > 0:
        raise _admin_err(
            status.HTTP_409_CONFLICT,
            f"Masih ada {active_users} akun pelanggan pada paket ini. "
            "Nonaktifkan saja paket agar pembeli baru tidak bisa memilihnya.",
        )

    session.delete(plan)
    session.commit()
    return {"deleted": True, "id": plan_id}


def _normalize_discount_fields(
    *,
    code: str,
    discount_type: str,
    discount_value: int,
    max_discount_rp: Optional[int],
    min_purchase_rp: int,
    target_plan_slug: Optional[str],
    target_cycle: Optional[str],
    max_uses: Optional[int],
    starts_at: Optional[int],
    expires_at: Optional[int],
) -> dict[str, Any]:
    clean_code = (code or "").strip().upper()
    if not DISCOUNT_CODE_RE.match(clean_code):
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Kode promo harus 2-32 karakter huruf kapital/angka/'-'/'_' tanpa spasi.",
        )
    dtype = (discount_type or "percent").strip().lower()
    if dtype not in ALLOWED_DISCOUNT_TYPES:
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Tipe diskon harus 'percent' atau 'fixed_rp'.",
        )
    dval = int(discount_value or 0)
    if dtype == "percent" and (dval < 1 or dval > 100):
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Nilai diskon persentase harus antara 1% hingga 100%.",
        )
    if dtype == "fixed_rp" and (dval < 1 or dval > 100_000_000):
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Potongan nominal harus antara Rp 1 hingga Rp 100.000.000.",
        )
    cap_rp = (
        int(max_discount_rp)
        if max_discount_rp is not None and int(max_discount_rp) > 0
        else None
    )
    min_rp = max(0, int(min_purchase_rp or 0))
    plan_slug = (target_plan_slug or "").strip().lower() or None
    cycle = (target_cycle or "").strip().lower() or None
    if cycle is not None and cycle not in ("monthly", "yearly"):
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Target siklus kode promo harus 'monthly', 'yearly', atau kosong (semua).",
        )
    limit_uses = int(max_uses) if max_uses is not None and int(max_uses) > 0 else None
    d_start = int(starts_at) if starts_at else None
    d_end = int(expires_at) if expires_at else None
    if d_start is not None and d_end is not None and d_end <= d_start:
        raise _admin_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Waktu berakhir kode promo harus lebih besar dari waktu mulai.",
        )
    return {
        "code": clean_code,
        "discount_type": dtype,
        "discount_value": dval,
        "max_discount_rp": cap_rp,
        "min_purchase_rp": min_rp,
        "target_plan_slug": plan_slug,
        "target_cycle": cycle,
        "max_uses": limit_uses,
        "starts_at": d_start,
        "expires_at": d_end,
    }


@router.get("/discounts", response_model=list[dict[str, Any]])
def list_admin_discounts(session: Session = Depends(get_db)):
    """Daftar seluruh kode promo/voucher diskon beserta statistik penggunaannya."""
    rows = session.scalars(
        select(DiscountCode).order_by(DiscountCode.id.desc())
    ).all()
    now_utc = int(time.time())
    return [serialize_discount_code(r, now_utc=now_utc) for r in rows]


@router.post("/discounts", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def create_admin_discount(
    req: AdminDiscountCreateRequest,
    session: Session = Depends(get_db),
):
    """Membuat kode promo/voucher baru untuk halaman checkout upgrade pelanggan."""
    v = _normalize_discount_fields(
        code=req.code,
        discount_type=req.discount_type,
        discount_value=req.discount_value,
        max_discount_rp=req.max_discount_rp,
        min_purchase_rp=req.min_purchase_rp,
        target_plan_slug=req.target_plan_slug,
        target_cycle=req.target_cycle,
        max_uses=req.max_uses,
        starts_at=req.starts_at,
        expires_at=req.expires_at,
    )
    if session.scalar(select(DiscountCode).where(DiscountCode.code == v["code"])):
        raise _admin_err(
            status.HTTP_409_CONFLICT,
            f"Kode promo '{v['code']}' sudah ada.",
        )

    now_utc = int(time.time())
    dc = DiscountCode(
        code=v["code"],
        label=(req.label or "").strip()[:80] or None,
        discount_type=v["discount_type"],
        discount_value=v["discount_value"],
        max_discount_rp=v["max_discount_rp"],
        min_purchase_rp=v["min_purchase_rp"],
        target_plan_slug=v["target_plan_slug"],
        target_cycle=v["target_cycle"],
        max_uses=v["max_uses"],
        used_count=0,
        starts_at=v["starts_at"],
        expires_at=v["expires_at"],
        is_active=1 if req.is_active else 0,
        created_at=now_utc,
        updated_at=now_utc,
    )
    session.add(dc)
    session.commit()
    session.refresh(dc)
    return serialize_discount_code(dc, now_utc=now_utc)


@router.patch("/discounts/{discount_id}", response_model=dict[str, Any])
def update_admin_discount(
    discount_id: int,
    req: AdminDiscountUpdateRequest,
    session: Session = Depends(get_db),
):
    """Memperbarui aturan, kuota, jadwal berlaku, atau status aktif kode promo."""
    dc = session.get(DiscountCode, discount_id)
    if not dc:
        raise _admin_err(status.HTTP_404_NOT_FOUND, "Kode promo tidak ditemukan.")

    v = _normalize_discount_fields(
        code=req.code if req.code is not None else dc.code,
        discount_type=req.discount_type if req.discount_type is not None else dc.discount_type,
        discount_value=req.discount_value if req.discount_value is not None else dc.discount_value,
        max_discount_rp=(
            req.max_discount_rp if "max_discount_rp" in req.model_fields_set else dc.max_discount_rp
        ),
        min_purchase_rp=(
            req.min_purchase_rp if req.min_purchase_rp is not None else dc.min_purchase_rp
        ),
        target_plan_slug=(
            req.target_plan_slug
            if "target_plan_slug" in req.model_fields_set
            else dc.target_plan_slug
        ),
        target_cycle=(
            req.target_cycle if "target_cycle" in req.model_fields_set else dc.target_cycle
        ),
        max_uses=req.max_uses if "max_uses" in req.model_fields_set else dc.max_uses,
        starts_at=req.starts_at if "starts_at" in req.model_fields_set else dc.starts_at,
        expires_at=req.expires_at if "expires_at" in req.model_fields_set else dc.expires_at,
    )

    if v["code"] != dc.code:
        existing_dc = session.scalar(
            select(DiscountCode).where(DiscountCode.code == v["code"], DiscountCode.id != dc.id)
        )
        if existing_dc:
            raise _admin_err(status.HTTP_409_CONFLICT, f"Kode promo '{v['code']}' sudah dipakai.")

    dc.code = v["code"]
    if req.label is not None:
        dc.label = req.label.strip()[:80] or None
    dc.discount_type = v["discount_type"]
    dc.discount_value = v["discount_value"]
    dc.max_discount_rp = v["max_discount_rp"]
    dc.min_purchase_rp = v["min_purchase_rp"]
    dc.target_plan_slug = v["target_plan_slug"]
    dc.target_cycle = v["target_cycle"]
    dc.max_uses = v["max_uses"]
    dc.starts_at = v["starts_at"]
    dc.expires_at = v["expires_at"]
    if req.is_active is not None:
        dc.is_active = 1 if req.is_active else 0
    now_utc = int(time.time())
    dc.updated_at = now_utc
    session.commit()
    session.refresh(dc)
    return serialize_discount_code(dc, now_utc=now_utc)


@router.delete("/discounts/{discount_id}", response_model=dict[str, Any])
def delete_admin_discount(discount_id: int, session: Session = Depends(get_db)):
    """Menghapus kode promo (histori tagihan lama tetap menyimpan snapshot teks kode)."""
    dc = session.get(DiscountCode, discount_id)
    if not dc:
        raise _admin_err(status.HTTP_404_NOT_FOUND, "Kode promo tidak ditemukan.")
    session.delete(dc)
    session.commit()
    return {"deleted": True, "id": discount_id}
