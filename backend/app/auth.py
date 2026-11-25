import hashlib
import hmac
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User

security_bearer = HTTPBearer(auto_error=False)
PBKDF2_ITERATIONS = 120_000


class LoginRateLimiter:
    """Rate limiter untuk endpoint login berbasis backoff bertahap tanpa sleep blocking."""

    def __init__(self, max_delay: int = 30) -> None:
        self.failure_count = 0
        self.lockout_until = 0.0
        self.max_delay = max_delay
        self._lock = threading.Lock()

    def check_rate_limit(self) -> tuple[bool, int]:
        """Memeriksa apakah login sedang dibatasi. Mengembalikan (is_limited, retry_after_detik)."""
        now = time.time()
        with self._lock:
            if now < self.lockout_until:
                retry_after = max(1, int(self.lockout_until - now + 0.99))
                return True, min(retry_after, self.max_delay)
            return False, 0

    def record_failure(self) -> int:
        """Mencatat kegagalan login.

        Jika >= 5 kegagalan berturut-turut, kunci sementara dengan backoff.
        """
        now = time.time()
        with self._lock:
            self.failure_count += 1
            if self.failure_count >= 5:
                # Backoff eksponensial: 2 detik, 4 detik, ..., maksimal 30 detik
                delay = min(self.max_delay, 2 ** (self.failure_count - 4))
                self.lockout_until = now + delay
                return delay
            return 0

    def record_success(self) -> None:
        """Mereset riwayat kegagalan setelah login berhasil."""
        with self._lock:
            self.failure_count = 0
            self.lockout_until = 0.0

    def reset(self) -> None:
        """Reset untuk keperluan pengujian."""
        with self._lock:
            self.failure_count = 0
            self.lockout_until = 0.0


login_limiter = LoginRateLimiter(max_delay=30)
user_login_limiter = LoginRateLimiter(max_delay=30)


def hash_password(plain_password: str) -> str:
    """Hash password tenant dengan PBKDF2-HMAC-SHA256 dan random salt."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        bytes.fromhex(salt),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def verify_user_password(plain_password: str, stored_hash: str) -> bool:
    """Verifikasi hash PBKDF2-HMAC-SHA256 secara constant-time."""
    if not stored_hash or stored_hash.startswith("!"):
        return False
    try:
        scheme, iter_str, salt, digest = stored_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            bytes.fromhex(salt),
            int(iter_str),
        ).hex()
        return hmac.compare_digest(calc.encode("utf-8"), digest.encode("utf-8"))
    except Exception:
        return False


def verify_password(plain_password: str) -> bool:
    """Verifikasi password admin dengan constant-time comparison."""
    settings = get_settings()
    configured_password = settings.dashboard_password or ""
    return hmac.compare_digest(plain_password.encode("utf-8"), configured_password.encode("utf-8"))


def create_access_token(
    subject: str = "dashboard_user",
    expires_delta: Optional[timedelta] = None,
    role: str = "admin",
    user_id: Optional[int] = None,
) -> str:
    """Membuat token JWT HS256 dengan klaim role (admin/user) dan user_id opsional."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(hours=24))
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if user_id is not None:
        payload["uid"] = int(user_id)
    secret = settings.jwt_secret or "dummy_secret_for_testing_purposes_only_32_chars"
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_token(token: str) -> dict[str, Any]:
    """Memverifikasi token JWT secara ketat menolak algoritma selain HS256."""
    settings = get_settings()
    secret = settings.jwt_secret or "dummy_secret_for_testing_purposes_only_32_chars"
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        if "role" not in payload:
            payload["role"] = "admin"
        return payload
    except jwt.PyJWTError as err:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": 401, "message": "Invalid or expired token"}},
            headers={"WWW-Authenticate": "Bearer"},
        ) from err


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """FastAPI Dependency untuk melindungi rute terotentikasi (user atau admin)."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": 401, "message": "Authentication required"}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = verify_token(credentials.credentials)
    role = payload.get("role", "admin")
    if role == "user":
        uid = payload.get("uid")
        user = session.get(User, int(uid)) if uid is not None else None
        if not user or not user.is_active:
            raise HTTPException(
                status_code=401,
                detail={"error": {"code": 401, "message": "User account inactive or not found"}},
                headers={"WWW-Authenticate": "Bearer"},
            )
        payload["user_id"] = user.id
        payload["user_name"] = user.name
        payload["user_email"] = user.email
    return payload


def get_current_admin(current: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """FastAPI Dependency ketat khusus role admin (tolak akun user biasa dengan 403)."""
    if current.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": 403, "message": "Admin privilege required"}},
        )
    return current
