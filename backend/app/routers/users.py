import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    user_login_limiter,
    verify_user_password,
)
from app.db import get_db
from app.models import User
from app.services.app_config import (
    get_active_terms_version,
    get_app_config_map,
    get_effective_google_oauth,
    is_registration_enabled,
    record_terms_consent,
)
from app.services.google_oauth import GoogleTokenError, verify_google_id_token

router = APIRouter(prefix="/api/users", tags=["Users"])

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
GOOGLE_ONLY_PASSWORD_SENTINEL = "!google_oauth_only"


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


def _serialize_user(
    u: User,
    active_terms_version: Optional[str] = None,
    require_terms_consent: bool = True,
) -> dict[str, Any]:
    accepted_ver = getattr(u, "terms_version_accepted", None)
    needs_reconsent = bool(
        require_terms_consent
        and active_terms_version
        and accepted_ver != active_terms_version
    )
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "role": "user",
        "auth_provider": getattr(u, "auth_provider", "local") or "local",
        "avatar_url": getattr(u, "avatar_url", None),
        "terms_version_accepted": accepted_ver,
        "terms_accepted_at": getattr(u, "terms_accepted_at", None),
        "needs_terms_reconsent": needs_reconsent,
        "is_active": bool(u.is_active),
        "created_at": u.created_at,
        "last_login_at": u.last_login_at,
    }


def _api_error(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"error": {"code": code, "message": message}})


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def register_user(
    req: UserRegisterRequest,
    request: Request,
    session: Session = Depends(get_db),
):
    """Registrasi akun pembeli baru untuk mode multi-tenant."""
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
    if len(req.password) < 6 or len(req.password) > 128:
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Kata sandi minimal 6 karakter",
        )

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
        ),
    }


@router.post("/login", response_model=dict[str, Any])
def login_user(
    req: UserLoginRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
):
    """Login akun pembeli dengan proteksi rate limit."""
    if req.accept_terms is False:
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Anda harus menyetujui Syarat Penggunaan & Kebijakan Privasi.",
        )

    is_limited, retry_after = user_login_limiter.check_rate_limit()
    if is_limited:
        response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
        response.headers["Retry-After"] = str(retry_after)
        return Response(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            content='{"error":{"code":429,"message":"Too many failed attempts. Retry later."}}',
            media_type="application/json",
        )

    clean_email = req.email.strip().lower()
    user = session.scalar(select(User).where(User.email == clean_email))
    if not user or not verify_user_password(req.password, user.password_hash):
        delay = user_login_limiter.record_failure()
        headers = {"Retry-After": str(delay)} if delay > 0 else {}
        return Response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers=headers,
            content='{"error":{"code":401,"message":"Email atau kata sandi salah"}}',
            media_type="application/json",
        )

    if not user.is_active:
        raise _api_error(
            status.HTTP_403_FORBIDDEN,
            "Akun dinonaktifkan oleh pengelola. Hubungi dukungan.",
        )

    user_login_limiter.record_success()
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
    response: Response,
    session: Session = Depends(get_db),
):
    """Autentikasi atau pendaftaran akun pelanggan via Google ID Token (Web & APK)."""
    if req.accept_terms is False:
        raise _api_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Anda harus menyetujui Syarat Penggunaan & Kebijakan Privasi.",
        )

    is_limited, retry_after = user_login_limiter.check_rate_limit()
    if is_limited:
        response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
        response.headers["Retry-After"] = str(retry_after)
        return Response(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            content='{"error":{"code":429,"message":"Too many failed attempts. Retry later."}}',
            media_type="application/json",
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
        delay = user_login_limiter.record_failure()
        headers = {"Retry-After": str(delay)} if delay > 0 else {}
        return Response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            headers=headers,
            content=json.dumps({"error": {"code": 401, "message": str(err)}}),
            media_type="application/json",
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
    user_login_limiter.record_success()

    token = create_access_token(subject=user.email, role="user", user_id=user.id)
    return {
        "token": token,
        "token_type": "bearer",
        "user": _serialize_user(
            user,
            active_terms_version=active_terms_ver,
            require_terms_consent=req_consent,
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
    )

