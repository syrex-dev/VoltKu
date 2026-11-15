import hmac
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

security_bearer = HTTPBearer(auto_error=False)


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


def verify_password(plain_password: str) -> bool:
    """Verifikasi password dashboard dengan constant-time comparison."""
    settings = get_settings()
    configured_password = settings.dashboard_password or ""
    return hmac.compare_digest(plain_password.encode("utf-8"), configured_password.encode("utf-8"))


def create_access_token(
    subject: str = "dashboard_user", expires_delta: Optional[timedelta] = None
) -> str:
    """Membuat token JWT dengan algoritma HS256."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(hours=24))
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    secret = settings.jwt_secret or "dummy_secret_for_testing_purposes_only_32_chars"
    token = jwt.encode(payload, secret, algorithm="HS256")
    return token


def verify_token(token: str) -> dict:
    """Memverifikasi token JWT secara ketat menolak algoritma selain HS256."""
    settings = get_settings()
    secret = settings.jwt_secret or "dummy_secret_for_testing_purposes_only_32_chars"
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload
    except jwt.PyJWTError as err:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": 401, "message": "Invalid or expired token"}},
            headers={"WWW-Authenticate": "Bearer"},
        ) from err


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> dict:
    """FastAPI Dependency untuk melindungi rute privat."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": 401, "message": "Authentication required"}},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_token(credentials.credentials)
