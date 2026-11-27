import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    forgot_password_limiter,
    get_current_user,
    get_trusted_client_ip,
    hash_password,
    register_limiter,
    reset_password_limiter,
    user_login_limiter,
    verify_user_password,
)
from app.db import get_db
from app.models import (
    PasswordResetToken,
    PaymentMethod,
    SubscriptionPlan,
    UpgradeRequest,
    User,
)
from app.services.app_config import (
    get_active_terms_version,
    get_app_config_map,
    get_effective_google_oauth,
    is_registration_enabled,
    record_terms_consent,
)
from app.services.email_service import issue_password_reset_token, send_password_reset_email
from app.services.google_oauth import GoogleTokenError, verify_google_id_token
from app.services.payments import (
    DEFAULT_PAYMENT_TTL_SECONDS,
    delete_private_image,
    expire_stale_awaiting_requests,
    generate_order_code,
    resolve_private_image_path,
    save_private_image,
)
from app.services.plans import (
    ACTIVE_UPGRADE_STATUSES,
    ensure_default_plans_seeded,
    evaluate_checkout_pricing,
    release_discount_usage,
    resolve_user_plan,
    serialize_upgrade_request,
)
from app.services.sync_state import compute_user_sync_state

router = APIRouter(prefix="/api/users", tags=["Users"])

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
GOOGLE_ONLY_PASSWORD_SENTINEL = "!google_oauth_only"
WEAK_PASSWORDS = {"123456", "12345678", "password", "qwerty", "admin123", "abcdef"}


class UserRegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    accept_terms: Optional[bool] = None
    accepted_terms_version: Optional[str] = None
    client_id: Optional[str] = None


class UserLoginRequest(BaseModel):
    email: str
    password: str
    accept_terms: Optional[bool] = None
    accepted_terms_version: Optional[str] = None
    client_id: Optional[str] = None


class GoogleLoginRequest(BaseModel):
    id_token: str
    accept_terms: Optional[bool] = None
    accepted_terms_version: Optional[str] = None
    client_id: Optional[str] = None


class UserTermsConsentRequest(BaseModel):
    accepted: bool
    terms_version: Optional[str] = None
    client_id: Optional[str] = None


class UpgradeSubmitRequest(BaseModel):
    plan_slug: Optional[str] = "pro"
    billing_cycle: str = "monthly"
    discount_code: Optional[str] = None
    payment_method_id: Optional[int] = None
    user_note: Optional[str] = None


class DiscountApplyRequest(BaseModel):
    plan_slug: str = "pro"
    billing_cycle: str = "monthly"
    discount_code: str


class UpgradeConfirmPaymentRequest(BaseModel):
    proof_base64: str
    user_note: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class UserProfileUpdateRequest(BaseModel):
    name: str


class UserChangePasswordRequest(BaseModel):
    current_password: Optional[str] = None
    new_password: str


PASSWORD_RESET_TTL_SECONDS = 30 * 60


def _validate_password_policy(password: str) -> None:
    if len(password) < 6 or len(password) > 128:
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Kata sandi minimal 6 karakter",
        )
    if password.strip().lower() in WEAK_PASSWORDS:
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Kata sandi terlalu lemah. Gunakan kombinasi huruf dan angka yang lebih kuat.",
        )


def _serialize_user(
    u: User,
    active_terms_version: Optional[str] = None,
    require_terms_consent: bool = True,
    *,
    session: Optional[Session] = None,
    cfg_map: Optional[dict[str, str]] = None,
    device_count: Optional[int] = None,
) -> dict[str, Any]:
    accepted_ver = getattr(u, "terms_version_accepted", None)
    needs_reconsent = bool(
        require_terms_consent
        and active_terms_version
        and accepted_ver != active_terms_version
    )
    payload: dict[str, Any] = {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "role": "user",
        "auth_provider": getattr(u, "auth_provider", "local") or "local",
        "has_local_password": not str(getattr(u, "password_hash", "") or "").startswith("!"),
        "avatar_url": getattr(u, "avatar_url", None),
        "terms_version_accepted": accepted_ver,
        "terms_accepted_at": getattr(u, "terms_accepted_at", None),
        "needs_terms_reconsent": needs_reconsent,
        "plan_tier": getattr(u, "plan_tier", "free") or "free",
        "plan_expires_at": getattr(u, "plan_expires_at", None),
        "plan_updated_at": getattr(u, "plan_updated_at", None),
        "is_active": bool(u.is_active),
        "created_at": u.created_at,
        "last_login_at": u.last_login_at,
    }
    if session is not None:
        resolved_cfg = cfg_map if cfg_map is not None else get_app_config_map(session)
        payload["plan"] = resolve_user_plan(
            session, u, resolved_cfg, device_count=device_count
        )
    return payload


def _api_error(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"error": {"code": code, "message": message}})


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def register_user(
    req: UserRegisterRequest,
    request: Request,
    session: Session = Depends(get_db),
):
    """Registrasi akun pembeli baru untuk mode multi-tenant dengan batas laju per IP."""
    client_ip = get_trusted_client_ip(request)
    is_limited, retry_after = register_limiter.check_and_record(client_ip)
    if is_limited:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            content={
                "error": {
                    "code": 429,
                    "message": "Terlalu banyak pendaftaran dari IP ini. Coba lagi nanti.",
                }
            },
        )

    if not is_registration_enabled(session):
        raise _api_error(
            status.HTTP_403_FORBIDDEN,
            "Pendaftaran akun baru saat ini ditutup oleh administrator.",
        )
    if req.accept_terms is False:
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Anda harus menyetujui Syarat Penggunaan & Kebijakan Privasi.",
        )

    clean_name = req.name.strip()
    clean_email = req.email.strip().lower()
    if len(clean_name) < 2 or len(clean_name) > 128:
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Nama lengkap harus antara 2 dan 128 karakter",
        )
    if not EMAIL_RE.match(clean_email) or len(clean_email) > 128:
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Format email tidak valid",
        )
    _validate_password_policy(req.password)

    existing = session.scalar(select(User).where(User.email == clean_email))
    if existing:
        raise _api_error(status.HTTP_409_CONFLICT, "Email sudah terdaftar. Silakan masuk.")

    now_utc = int(datetime.now(timezone.utc).timestamp())
    user = User(
        name=clean_name,
        email=clean_email,
        password_hash=hash_password(req.password),
        is_active=1,
        created_at=now_utc,
        last_login_at=now_utc,
    )
    session.add(user)
    session.flush()

    cfg_map = get_app_config_map(session)
    active_terms_ver = get_active_terms_version(session, cfg_map)
    req_consent = cfg_map.get("require_terms_consent", "true").lower() in ("true", "1")

    if req.accept_terms is True:
        record_terms_consent(
            session,
            user=user,
            email_snapshot=user.email,
            client_id=req.client_id,
            accepted_via="register",
            accepted_terms_version=req.accepted_terms_version,
            request=request,
        )

    session.commit()
    session.refresh(user)

    token = create_access_token(subject=user.email, role="user", user_id=user.id)
    return {
        "token": token,
        "token_type": "bearer",
        "user": _serialize_user(
            user,
            active_terms_version=active_terms_ver,
            require_terms_consent=req_consent,
            session=session,
            cfg_map=cfg_map,
            device_count=0,
        ),
    }


@router.post("/login", response_model=dict[str, Any])
def login_user(
    req: UserLoginRequest,
    request: Request,
    session: Session = Depends(get_db),
):
    """Login akun pembeli dengan proteksi rate limit per IP."""
    if req.accept_terms is False:
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Anda harus menyetujui Syarat Penggunaan & Kebijakan Privasi.",
        )

    client_ip = get_trusted_client_ip(request)
    is_limited, retry_after = user_login_limiter.check_rate_limit(client_ip)
    if is_limited:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            content={
                "error": {"code": 429, "message": "Too many failed attempts. Retry later."}
            },
        )

    clean_email = req.email.strip().lower()
    user = session.scalar(select(User).where(User.email == clean_email))
    if not user or not verify_user_password(req.password, user.password_hash):
        delay = user_login_limiter.record_failure(client_ip)
        headers = {"Retry-After": str(delay)} if delay > 0 else {}
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers=headers,
            content={"error": {"code": 401, "message": "Email atau kata sandi salah"}},
        )

    if not user.is_active:
        raise _api_error(
            status.HTTP_403_FORBIDDEN,
            "Akun dinonaktifkan oleh pengelola. Hubungi dukungan.",
        )

    user_login_limiter.record_success(client_ip)
    user.last_login_at = int(datetime.now(timezone.utc).timestamp())

    cfg_map = get_app_config_map(session)
    active_terms_ver = get_active_terms_version(session, cfg_map)
    req_consent = cfg_map.get("require_terms_consent", "true").lower() in ("true", "1")

    if req.accept_terms is True and user.terms_version_accepted != active_terms_ver:
        record_terms_consent(
            session,
            user=user,
            email_snapshot=user.email,
            client_id=req.client_id,
            accepted_via="login",
            accepted_terms_version=req.accepted_terms_version,
            request=request,
        )

    session.commit()
    session.refresh(user)

    token = create_access_token(subject=user.email, role="user", user_id=user.id)
    return {
        "token": token,
        "token_type": "bearer",
        "user": _serialize_user(
            user,
            active_terms_version=active_terms_ver,
            require_terms_consent=req_consent,
            session=session,
            cfg_map=cfg_map,
        ),
    }


@router.get("/oauth-config", response_model=dict[str, Any])
def get_oauth_config(session: Session = Depends(get_db)):
    """Konfigurasi publik klien untuk Login Google & versi persetujuan Syarat Penggunaan."""
    cfg_map = get_app_config_map(session)
    oauth = get_effective_google_oauth(session, cfg_map)
    terms_ver = get_active_terms_version(session, cfg_map)
    return {
        "google_enabled": oauth["google_enabled"],
        "google_client_id": oauth["google_client_id"] if oauth["google_auth_enabled"] else None,
        "google_android_client_id": (
            oauth["google_android_client_id"] if oauth["google_auth_enabled"] else None
        ),
        "terms_version": terms_ver,
    }


@router.post("/google", response_model=dict[str, Any])
def login_with_google(
    req: GoogleLoginRequest,
    request: Request,
    session: Session = Depends(get_db),
):
    """Autentikasi atau pendaftaran akun pelanggan via Google ID Token (Web & APK)."""
    if req.accept_terms is False:
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Anda harus menyetujui Syarat Penggunaan & Kebijakan Privasi.",
        )

    client_ip = get_trusted_client_ip(request)
    is_limited, retry_after = user_login_limiter.check_rate_limit(client_ip)
    if is_limited:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            content={
                "error": {"code": 429, "message": "Too many failed attempts. Retry later."}
            },
        )

    cfg_map = get_app_config_map(session)
    oauth = get_effective_google_oauth(session, cfg_map)
    if not oauth["google_auth_enabled"]:
        raise _api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Login Google sedang dinonaktifkan oleh pengelola.",
        )
    if not oauth["allowed_client_ids"]:
        raise _api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Login Google belum diaktifkan di server. Hubungi admin atau masuk dengan email.",
        )

    try:
        g_profile = verify_google_id_token(req.id_token, oauth["allowed_client_ids"])
    except GoogleTokenError as err:
        delay = user_login_limiter.record_failure(client_ip)
        headers = {"Retry-After": str(delay)} if delay > 0 else {}
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers=headers,
            content={"error": {"code": 401, "message": str(err)}},
        )

    now_utc = int(datetime.now(timezone.utc).timestamp())
    user = session.scalar(select(User).where(User.google_sub == g_profile["sub"]))
    if not user:
        user = session.scalar(select(User).where(User.email == g_profile["email"]))

    if user:
        if not user.is_active:
            raise _api_error(
                status.HTTP_403_FORBIDDEN,
                "Akun dinonaktifkan oleh pengelola. Hubungi dukungan.",
            )
        user.google_sub = g_profile["sub"]
        if g_profile.get("avatar_url"):
            user.avatar_url = g_profile["avatar_url"]
        has_local_pw = bool(user.password_hash and not user.password_hash.startswith("!"))
        user.auth_provider = "both" if has_local_pw else "google"
        user.last_login_at = now_utc
    else:
        if not is_registration_enabled(session):
            raise _api_error(
                status.HTTP_403_FORBIDDEN,
                "Pendaftaran akun baru saat ini ditutup oleh administrator.",
            )
        user = User(
            name=g_profile["name"] or "Pengguna VoltKu",
            email=g_profile["email"],
            password_hash=GOOGLE_ONLY_PASSWORD_SENTINEL,
            auth_provider="google",
            google_sub=g_profile["sub"],
            avatar_url=g_profile.get("avatar_url"),
            is_active=1,
            created_at=now_utc,
            last_login_at=now_utc,
        )
        session.add(user)
        session.flush()

    active_terms_ver = get_active_terms_version(session, cfg_map)
    req_consent = cfg_map.get("require_terms_consent", "true").lower() in ("true", "1")
    if req.accept_terms is True and user.terms_version_accepted != active_terms_ver:
        record_terms_consent(
            session,
            user=user,
            email_snapshot=user.email,
            client_id=req.client_id,
            accepted_via="google",
            accepted_terms_version=req.accepted_terms_version,
            request=request,
        )

    session.commit()
    session.refresh(user)
    user_login_limiter.record_success(client_ip)

    token = create_access_token(subject=user.email, role="user", user_id=user.id)
    return {
        "token": token,
        "token_type": "bearer",
        "user": _serialize_user(
            user,
            active_terms_version=active_terms_ver,
            require_terms_consent=req_consent,
            session=session,
            cfg_map=cfg_map,
        ),
    }


@router.get("/me", response_model=dict[str, Any])
def get_my_profile(
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Mengembalikan profil akun pembeli yang sedang login."""
    if current.get("role") == "admin":
        return {
            "id": 0,
            "name": "Administrator",
            "email": "admin",
            "role": "admin",
            "is_active": True,
            "needs_terms_reconsent": False,
        }
    uid = current.get("user_id")
    user = session.get(User, int(uid)) if uid is not None else None
    if not user:
        raise _api_error(status.HTTP_404_NOT_FOUND, "User not found")
    cfg_map = get_app_config_map(session)
    active_terms_ver = get_active_terms_version(session, cfg_map)
    req_consent = cfg_map.get("require_terms_consent", "true").lower() in ("true", "1")
    return _serialize_user(
        user,
        active_terms_version=active_terms_ver,
        require_terms_consent=req_consent,
        session=session,
        cfg_map=cfg_map,
    )


@router.patch("/me", response_model=dict[str, Any])
def update_my_profile(
    req: UserProfileUpdateRequest,
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Memperbarui nama tampilan profil akun pembeli yang sedang login."""
    if current.get("role") != "user" or current.get("user_id") is None:
        raise _api_error(status.HTTP_403_FORBIDDEN, "Hanya berlaku untuk akun pengguna.")
    user = session.get(User, int(current["user_id"]))
    if not user:
        raise _api_error(status.HTTP_404_NOT_FOUND, "User not found")

    clean_name = (req.name or "").strip()
    if len(clean_name) < 2 or len(clean_name) > 100:
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Nama lengkap harus antara 2 dan 100 karakter.",
        )

    user.name = clean_name
    session.commit()
    session.refresh(user)
    cfg_map = get_app_config_map(session)
    active_terms_ver = get_active_terms_version(session, cfg_map)
    req_consent = cfg_map.get("require_terms_consent", "true").lower() in ("true", "1")
    return _serialize_user(
        user,
        active_terms_version=active_terms_ver,
        require_terms_consent=req_consent,
        session=session,
        cfg_map=cfg_map,
    )


@router.post("/change-password", response_model=dict[str, Any])
def change_my_password(
    req: UserChangePasswordRequest,
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Mengubah kata sandi akun (atau menambah sandi lokal bagi pengguna Google)."""
    if current.get("role") != "user" or current.get("user_id") is None:
        raise _api_error(status.HTTP_403_FORBIDDEN, "Hanya berlaku untuk akun pengguna.")
    user = session.get(User, int(current["user_id"]))
    if not user or not user.is_active:
        raise _api_error(status.HTTP_404_NOT_FOUND, "User not found")

    has_local = not str(user.password_hash or "").startswith("!")
    if has_local:
        if not req.current_password or not verify_user_password(
            req.current_password, user.password_hash
        ):
            raise _api_error(status.HTTP_401_UNAUTHORIZED, "Kata sandi saat ini salah.")

    _validate_password_policy(req.new_password)
    if has_local and req.current_password == req.new_password:
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Kata sandi baru harus berbeda dari kata sandi saat ini.",
        )

    user.password_hash = hash_password(req.new_password)
    if (user.auth_provider or "").lower() == "google":
        user.auth_provider = "both"
    now_utc = int(datetime.now(timezone.utc).timestamp())
    session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now_utc)
    )
    session.commit()
    return {
        "changed": True,
        "message": "Kata sandi berhasil diperbarui.",
    }


@router.get("/upgrade-request", response_model=list[dict[str, Any]])
def list_my_upgrade_requests(
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Riwayat pengajuan upgrade paket & tagihan akun pengguna saat ini."""
    uid = current.get("user_id")
    if current.get("role") != "user" or uid is None:
        return []
    expire_stale_awaiting_requests(session, user_id=int(uid))
    session.commit()
    rows = session.scalars(
        select(UpgradeRequest)
        .where(UpgradeRequest.user_id == int(uid))
        .order_by(UpgradeRequest.created_at.desc())
        .limit(20)
    ).all()
    return [serialize_upgrade_request(r) for r in rows]


def _resolve_active_paid_plan(
    session: Session,
    plan_slug: Optional[str],
    cfg_map: dict[str, str],
) -> SubscriptionPlan:
    plans = ensure_default_plans_seeded(session, cfg_map)
    clean_slug = (plan_slug or "pro").strip().lower()
    target = next((p for p in plans if p.slug == clean_slug), None)
    if target is None and clean_slug == "pro":
        target = next(
            (p for p in plans if not p.is_default_free and p.slug != "free" and p.is_active),
            None,
        )
    if not target or not target.is_active:
        raise _api_error(
            status.HTTP_404_NOT_FOUND,
            f"Paket langganan '{clean_slug}' tidak ditemukan atau sedang nonaktif.",
        )
    if target.is_default_free or target.slug == "free":
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Pilih paket berbayar untuk membuat tagihan upgrade.",
        )
    return target


@router.post("/apply-discount", response_model=dict[str, Any])
def preview_discount_code(
    req: DiscountApplyRequest,
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Validasi kode promo/kupon terhadap paket & siklus berlangganan sebelum checkout."""
    if current.get("role") != "user" or current.get("user_id") is None:
        raise _api_error(status.HTTP_403_FORBIDDEN, "Hanya berlaku untuk akun pengguna.")

    cycle = (req.billing_cycle or "monthly").strip().lower()
    if cycle not in ("monthly", "yearly"):
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "billing_cycle harus 'monthly' atau 'yearly'.",
        )
    if not (req.discount_code or "").strip():
        raise _api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Masukkan kode promo.")

    cfg_map = get_app_config_map(session)
    plan = _resolve_active_paid_plan(session, req.plan_slug, cfg_map)
    now_utc = int(datetime.now(timezone.utc).timestamp())
    quote = evaluate_checkout_pricing(
        session,
        plan=plan,
        billing_cycle=cycle,
        discount_code_raw=req.discount_code,
        now_utc=now_utc,
    )
    return {
        "valid": True,
        "plan_slug": quote["plan_slug"],
        "plan_name": quote["plan_name"],
        "billing_cycle": quote["billing_cycle"],
        "base_amount_rp": quote["base_amount_rp"],
        "promo_discount_rp": quote["promo_discount_rp"],
        "promo_label": quote["promo_label"],
        "discount_code": quote["discount_code"],
        "discount_label": quote["discount_label"],
        "voucher_discount_rp": quote["voucher_discount_rp"],
        "final_amount_rp": quote["final_amount_rp"],
    }


@router.post("/upgrade-request", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def submit_upgrade_request(
    req: UpgradeSubmitRequest,
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Membuat tagihan/pengajuan upgrade manual ke paket pilihan user beserta promo & voucher."""
    uid = current.get("user_id")
    if current.get("role") != "user" or uid is None:
        raise _api_error(status.HTTP_403_FORBIDDEN, "Hanya berlaku untuk akun pengguna.")

    user = session.get(User, int(uid))
    if not user:
        raise _api_error(status.HTTP_404_NOT_FOUND, "User not found")

    expire_stale_awaiting_requests(session, user_id=user.id)

    cycle = (req.billing_cycle or "monthly").strip().lower()
    if cycle not in ("monthly", "yearly"):
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "billing_cycle harus 'monthly' atau 'yearly'.",
        )

    existing_pending = session.scalar(
        select(UpgradeRequest).where(
            UpgradeRequest.user_id == user.id,
            UpgradeRequest.status.in_(ACTIVE_UPGRADE_STATUSES),
        )
    )
    if existing_pending:
        raise _api_error(
            status.HTTP_409_CONFLICT,
            "Anda masih memiliki tagihan upgrade yang sedang berjalan.",
        )

    pm: Optional[PaymentMethod] = None
    if req.payment_method_id is not None:
        pm = session.get(PaymentMethod, int(req.payment_method_id))
        if not pm or not pm.is_active:
            raise _api_error(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Metode pembayaran tidak ditemukan atau sedang nonaktif.",
            )

    cfg_map = get_app_config_map(session)
    target_plan = _resolve_active_paid_plan(session, req.plan_slug, cfg_map)
    now_utc = int(datetime.now(timezone.utc).timestamp())
    quote = evaluate_checkout_pricing(
        session,
        plan=target_plan,
        billing_cycle=cycle,
        discount_code_raw=req.discount_code,
        now_utc=now_utc,
    )
    dc = quote["discount_code_obj"]
    if dc is not None:
        dc.used_count = int(dc.used_count or 0) + 1

    clean_note = req.user_note.strip()[:255] if req.user_note and req.user_note.strip() else None

    entry = UpgradeRequest(
        user_id=user.id,
        order_code=generate_order_code(now_utc),
        requested_tier=target_plan.slug,
        plan_id=target_plan.id,
        plan_name_snapshot=target_plan.name,
        billing_cycle=cycle,
        base_amount_rp=quote["base_amount_rp"],
        promo_discount_rp=quote["promo_discount_rp"],
        discount_code_id=dc.id if dc else None,
        discount_code=quote["discount_code"],
        voucher_discount_rp=quote["voucher_discount_rp"],
        amount_rp=quote["final_amount_rp"],
        payment_method_id=pm.id if pm else None,
        payment_method_type=pm.type if pm else None,
        payment_method_label=pm.label if pm else None,
        payment_account_number=pm.account_number if pm else None,
        payment_account_holder=pm.account_holder if pm else None,
        payment_instructions=pm.instructions if pm else None,
        status="awaiting_payment" if pm else "pending",
        user_note=clean_note,
        expires_at=(now_utc + DEFAULT_PAYMENT_TTL_SECONDS) if pm else None,
        created_at=now_utc,
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return serialize_upgrade_request(entry, user=user)


@router.post("/upgrade-requests/{request_id}/confirm-payment", response_model=dict[str, Any])
def confirm_upgrade_payment(
    request_id: int,
    req: UpgradeConfirmPaymentRequest,
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Pelanggan mengunggah bukti transfer untuk tagihan upgrade (status -> verifying)."""
    uid = current.get("user_id")
    if current.get("role") != "user" or uid is None:
        raise _api_error(status.HTTP_403_FORBIDDEN, "Hanya berlaku untuk akun pengguna.")

    entry = session.get(UpgradeRequest, request_id)
    if not entry or entry.user_id != int(uid):
        raise _api_error(status.HTTP_404_NOT_FOUND, "Tagihan upgrade tidak ditemukan.")

    now_utc = int(datetime.now(timezone.utc).timestamp())
    if entry.status == "awaiting_payment" and entry.expires_at and entry.expires_at <= now_utc:
        entry.status = "expired"
        entry.resolved_at = now_utc
        release_discount_usage(session, entry)
        session.commit()
        raise _api_error(
            status.HTTP_409_CONFLICT,
            "Batas waktu pembayaran telah kedaluwarsa. Silakan buat tagihan baru.",
        )

    if entry.status not in ("pending", "awaiting_payment"):
        raise _api_error(
            status.HTTP_409_CONFLICT,
            f"Tagihan berstatus '{entry.status}' tidak dapat dikirim bukti bayar.",
        )

    try:
        proof_rel = save_private_image("payment_proofs", req.proof_base64)
    except ValueError as err:
        raise _api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, str(err)) from err

    old_proof = entry.payment_proof_path
    entry.payment_proof_path = proof_rel
    entry.status = "verifying"
    entry.submitted_at = now_utc
    if req.user_note and req.user_note.strip():
        entry.user_note = req.user_note.strip()[:255]

    session.commit()
    session.refresh(entry)
    if old_proof and old_proof != proof_rel:
        delete_private_image(old_proof)

    user = session.get(User, int(uid))
    return serialize_upgrade_request(entry, user=user)


@router.post("/upgrade-requests/{request_id}/cancel", response_model=dict[str, Any])
def cancel_upgrade_request(
    request_id: int,
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Membatalkan tagihan upgrade yang belum dibayar / belum diverifikasi."""
    uid = current.get("user_id")
    if current.get("role") != "user" or uid is None:
        raise _api_error(status.HTTP_403_FORBIDDEN, "Hanya berlaku untuk akun pengguna.")

    entry = session.get(UpgradeRequest, request_id)
    if not entry or entry.user_id != int(uid):
        raise _api_error(status.HTTP_404_NOT_FOUND, "Tagihan upgrade tidak ditemukan.")

    if entry.status not in ("pending", "awaiting_payment"):
        raise _api_error(
            status.HTTP_409_CONFLICT,
            f"Tagihan berstatus '{entry.status}' tidak dapat dibatalkan.",
        )

    entry.status = "cancelled"
    entry.resolved_at = int(datetime.now(timezone.utc).timestamp())
    release_discount_usage(session, entry)
    session.commit()
    session.refresh(entry)
    user = session.get(User, int(uid))
    return serialize_upgrade_request(entry, user=user)


@router.get("/upgrade-requests/{request_id}/proof")
def get_my_upgrade_proof_image(
    request_id: int,
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Mengambil foto bukti bayar untuk pemilik tagihan atau Admin."""
    entry = session.get(UpgradeRequest, request_id)
    if not entry:
        raise _api_error(status.HTTP_404_NOT_FOUND, "Tagihan upgrade tidak ditemukan.")
    if current.get("role") != "admin" and entry.user_id != current.get("user_id"):
        raise _api_error(status.HTTP_403_FORBIDDEN, "Akses ditolak.")

    resolved = resolve_private_image_path(entry.payment_proof_path)
    if not resolved:
        raise _api_error(status.HTTP_404_NOT_FOUND, "Bukti pembayaran belum tersedia.")
    file_path, media_type = resolved
    return FileResponse(
        file_path,
        media_type=media_type,
        headers={"Cache-Control": "private, no-store"},
    )


@router.post("/terms-consent", response_model=dict[str, Any])
def submit_user_terms_consent(
    req: UserTermsConsentRequest,
    request: Request,
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Simpan atau perbarui persetujuan Syarat Penggunaan & Privasi akun yang sedang login."""
    if not req.accepted:
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Persetujuan harus bernilai true untuk melanjutkan penggunaan layanan.",
        )

    uid = current.get("user_id")
    if current.get("role") != "user" or uid is None:
        raise _api_error(status.HTTP_403_FORBIDDEN, "Hanya berlaku untuk akun pengguna.")

    user = session.get(User, int(uid))
    if not user:
        raise _api_error(status.HTTP_404_NOT_FOUND, "User not found")

    record_terms_consent(
        session,
        user=user,
        email_snapshot=user.email,
        client_id=req.client_id,
        accepted_via="reconsent",
        accepted_terms_version=req.terms_version,
        request=request,
    )
    session.commit()
    session.refresh(user)

    cfg_map = get_app_config_map(session)
    active_terms_ver = get_active_terms_version(session, cfg_map)
    req_consent = cfg_map.get("require_terms_consent", "true").lower() in ("true", "1")
    return _serialize_user(
        user,
        active_terms_version=active_terms_ver,
        require_terms_consent=req_consent,
        session=session,
        cfg_map=cfg_map,
    )


@router.post("/forgot-password", response_model=dict[str, Any])
def request_password_reset(
    req: ForgotPasswordRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
):
    """Mengirim tautan reset kata sandi ke email user secara aman (anti-enumerasi + rate limit)."""
    client_ip = get_trusted_client_ip(request)
    is_limited, retry_after = forgot_password_limiter.check_and_record(f"ip:{client_ip}")
    if is_limited:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            content={
                "error": {
                    "code": 429,
                    "message": "Terlalu banyak permintaan reset kata sandi. Coba lagi nanti.",
                }
            },
        )

    clean_email = (req.email or "").strip().lower()
    if not EMAIL_RE.match(clean_email) or len(clean_email) > 128:
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Format email tidak valid.",
        )

    neutral_response = {
        "sent": True,
        "message": (
            "Jika email terdaftar di VoltKu, tautan reset kata sandi telah dikirim "
            "dan berlaku selama 30 menit."
        ),
    }

    user = session.scalar(select(User).where(User.email == clean_email))
    if not user or not user.is_active:
        return neutral_response

    email_limited, _ = forgot_password_limiter.check_and_record(f"email:{clean_email}")
    if email_limited:
        return neutral_response

    raw_token = issue_password_reset_token(session, user.id)

    background_tasks.add_task(
        send_password_reset_email,
        to_email=user.email,
        user_name=user.name,
        raw_token=raw_token,
        expires_minutes=30,
    )
    return neutral_response


def _mask_email(email: str) -> str:
    clean = (email or "").strip()
    if "@" not in clean:
        return "***"
    local, domain = clean.split("@", 1)
    prefix = local[:2] if len(local) >= 2 else local[:1]
    return f"{prefix}***@{domain}"


@router.get("/reset-password/status", response_model=dict[str, Any])
def get_reset_token_status(
    token: str = Query(""),
    session: Session = Depends(get_db),
):
    """Memeriksa keabsahan awal tautan reset kata sandi untuk tampilan halaman standalone."""
    raw_token = (token or "").strip()
    if len(raw_token) < 16 or len(raw_token) > 256:
        return {"valid": False, "reason": "missing_or_invalid"}

    now_utc = int(datetime.now(timezone.utc).timestamp())
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    reset_row = session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    if not reset_row:
        return {"valid": False, "reason": "invalid"}
    if reset_row.used_at is not None:
        return {"valid": False, "reason": "used"}
    if reset_row.expires_at <= now_utc:
        return {"valid": False, "reason": "expired"}

    user = session.get(User, reset_row.user_id)
    if not user or not user.is_active:
        return {"valid": False, "reason": "inactive"}

    return {
        "valid": True,
        "email_masked": _mask_email(user.email),
        "expires_in_seconds": max(0, int(reset_row.expires_at - now_utc)),
    }


@router.post("/reset-password", response_model=dict[str, Any])
def reset_password_with_token(
    req: ResetPasswordRequest,
    request: Request,
    session: Session = Depends(get_db),
):
    """Menyetel ulang kata sandi menggunakan token sekali pakai dari email."""
    client_ip = get_trusted_client_ip(request)
    is_limited, retry_after = reset_password_limiter.check_and_record(f"ip:{client_ip}")
    if is_limited:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            content={
                "error": {
                    "code": 429,
                    "message": "Terlalu banyak percobaan reset. Coba lagi nanti.",
                }
            },
        )

    raw_token = (req.token or "").strip()
    if len(raw_token) < 16 or len(raw_token) > 256:
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "Tautan reset kata sandi tidak valid atau sudah kedaluwarsa.",
        )

    _validate_password_policy(req.new_password)

    now_utc = int(datetime.now(timezone.utc).timestamp())
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    reset_row = session.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )
    if not reset_row or reset_row.used_at is not None or reset_row.expires_at <= now_utc:
        raise _api_error(
            status.HTTP_400_BAD_REQUEST,
            "Tautan reset kata sandi tidak valid atau sudah kedaluwarsa.",
        )

    user = session.get(User, reset_row.user_id)
    if not user or not user.is_active:
        raise _api_error(
            status.HTTP_403_FORBIDDEN,
            "Akun tidak ditemukan atau sedang dinonaktifkan.",
        )

    has_local_pw = not str(getattr(user, "password_hash", "") or "").startswith("!")
    if has_local_pw and verify_user_password(req.new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "reason": "same_as_old_password",
                    "message": (
                        "Jangan sama dengan kata sandi lama Anda. Kata sandi tersebut masih aktif "
                        "— Anda dapat langsung masuk atau buat kata sandi baru yang berbeda."
                    ),
                }
            },
        )

    user.password_hash = hash_password(req.new_password)
    if (user.auth_provider or "").lower() == "google":
        user.auth_provider = "both"
    session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now_utc)
    )
    session.commit()
    return {
        "reset": True,
        "message": "Kata sandi berhasil diperbarui. Silakan masuk dengan kata sandi baru Anda.",
    }


@router.get("/sync-state", response_model=dict[str, Any])
def get_user_sync_state(
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Status revisi ringan untuk sinkronisasi real-time paket, notif, & perangkat pengguna."""
    uid = current.get("user_id")
    if current.get("role") != "user" or uid is None:
        raise _api_error(status.HTTP_403_FORBIDDEN, "Hanya berlaku untuk akun pengguna.")
    return compute_user_sync_state(session, user_id=int(uid))


