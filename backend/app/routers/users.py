import json
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
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
from app.config import get_settings
from app.db import get_db
from app.models import User
from app.services.google_oauth import GoogleTokenError, verify_google_id_token

router = APIRouter(prefix="/api/users", tags=["Users"])

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
GOOGLE_ONLY_PASSWORD_SENTINEL = "!google_oauth_only"


class UserRegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class UserLoginRequest(BaseModel):
    email: str
    password: str


class GoogleLoginRequest(BaseModel):
    id_token: str


def _serialize_user(u: User) -> dict[str, Any]:
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "role": "user",
        "auth_provider": getattr(u, "auth_provider", "local") or "local",
        "avatar_url": getattr(u, "avatar_url", None),
        "is_active": bool(u.is_active),
        "created_at": u.created_at,
        "last_login_at": u.last_login_at,
    }


def _api_error(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"error": {"code": code, "message": message}})


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=dict[str, Any])
def register_user(req: UserRegisterRequest, session: Session = Depends(get_db)):
    """Registrasi akun pembeli baru untuk mode multi-tenant."""
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
    session.commit()
    session.refresh(user)

    token = create_access_token(subject=user.email, role="user", user_id=user.id)
    return {
        "token": token,
        "token_type": "bearer",
        "user": _serialize_user(user),
    }


@router.post("/login", response_model=dict[str, Any])
def login_user(
    req: UserLoginRequest,
    response: Response,
    session: Session = Depends(get_db),
):
    """Login akun pembeli dengan proteksi rate limit."""
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
    session.commit()
    session.refresh(user)

    token = create_access_token(subject=user.email, role="user", user_id=user.id)
    return {
        "token": token,
        "token_type": "bearer",
        "user": _serialize_user(user),
    }


@router.get("/oauth-config", response_model=dict[str, Any])
def get_oauth_config():
    """Konfigurasi publik klien untuk Login Google & versi persetujuan Syarat Penggunaan."""
    cfg = get_settings()
    web_cid = (
        cfg.google_client_id.strip()
        if cfg.google_client_id and cfg.google_client_id.strip()
        else None
    )
    android_cid = (
        cfg.google_android_client_id.strip()
        if cfg.google_android_client_id and cfg.google_android_client_id.strip()
        else None
    )
    return {
        "google_enabled": bool(cfg.allowed_google_client_ids),
        "google_client_id": web_cid,
        "google_android_client_id": android_cid,
        "terms_version": cfg.terms_version,
    }


@router.post("/google", response_model=dict[str, Any])
def login_with_google(
    req: GoogleLoginRequest,
    response: Response,
    session: Session = Depends(get_db),
):
    """Autentikasi atau pendaftaran akun pelanggan via Google ID Token (Web & APK)."""
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

    cfg = get_settings()
    if not cfg.allowed_google_client_ids:
        raise _api_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Login Google belum diaktifkan di server. Hubungi admin atau masuk dengan email.",
        )

    try:
        g_profile = verify_google_id_token(req.id_token, cfg.allowed_google_client_ids)
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

    session.commit()
    session.refresh(user)
    user_login_limiter.record_success()

    token = create_access_token(subject=user.email, role="user", user_id=user.id)
    return {
        "token": token,
        "token_type": "bearer",
        "user": _serialize_user(user),
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
        }
    uid = current.get("user_id")
    user = session.get(User, int(uid)) if uid is not None else None
    if not user:
        raise _api_error(status.HTTP_404_NOT_FOUND, "User not found")
    return _serialize_user(user)

