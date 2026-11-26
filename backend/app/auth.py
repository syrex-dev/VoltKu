import hashlib
import hmac
import secrets
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User

security_bearer = HTTPBearer(auto_error=False)
PBKDF2_ITERATIONS = 120_000
_TRUSTED_PROXY_HOSTS = {"127.0.0.1", "::1", "testclient"}
_MAX_RATE_LIMIT_KEYS = 10_000


def get_trusted_client_ip(request: Optional[Request]) -> str:
    """Ekstrak IP klien secara aman: hanya percaya header proxy bila berasal dari loopback lokal."""
    if request is None:
        return "global"
    peer_host = request.client.host.strip() if (request.client and request.client.host) else ""
    if peer_host in _TRUSTED_PROXY_HOSTS or not peer_host:
        cf_ip = request.headers.get("cf-connecting-ip")
        if cf_ip and cf_ip.strip():
            return cf_ip.strip()[:64]
        x_real = request.headers.get("x-real-ip")
        if x_real and x_real.strip():
            return x_real.strip()[:64]
        xff = request.headers.get("x-forwarded-for")
        if xff and xff.strip():
            return xff.split(",")[0].strip()[:64]
    return (peer_host or "unknown")[:64]


class _FailureBucket:
    __slots__ = ("failure_count", "lockout_until", "last_seen")

    def __init__(self) -> None:
        self.failure_count = 0
        self.lockout_until = 0.0
        self.last_seen = time.monotonic()


class LoginRateLimiter:
    """Rate limiter untuk endpoint login berbasis backoff bertahap per IP tanpa sleep blocking."""

    def __init__(self, max_delay: int = 30) -> None:
        self.max_delay = max_delay
        self._buckets: dict[str, _FailureBucket] = {}
        self._lock = threading.Lock()

    def _evict_if_full(self) -> None:
        if len(self._buckets) < _MAX_RATE_LIMIT_KEYS:
            return
        now_mono = time.monotonic()
        expired = [k for k, v in self._buckets.items() if (now_mono - v.last_seen) > 3600]
        for k in expired:
            del self._buckets[k]
        while len(self._buckets) >= _MAX_RATE_LIMIT_KEYS:
            oldest_key = min(self._buckets, key=lambda k: self._buckets[k].last_seen)
            del self._buckets[oldest_key]

    def check_rate_limit(self, key: str = "global") -> tuple[bool, int]:
        """Memeriksa apakah key/IP dibatasi. Mengembalikan (is_limited, retry_after_detik)."""
        now = time.time()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket and now < bucket.lockout_until:
                retry_after = max(1, int(bucket.lockout_until - now + 0.99))
                return True, min(retry_after, self.max_delay)
            return False, 0

    def record_failure(self, key: str = "global") -> int:
        """Mencatat kegagalan login untuk key/IP. Backoff aktif setelah >= 5 kegagalan."""
        now = time.time()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                self._evict_if_full()
                bucket = _FailureBucket()
                self._buckets[key] = bucket
            bucket.last_seen = time.monotonic()
            bucket.failure_count += 1
            if bucket.failure_count >= 5:
                delay = min(self.max_delay, 2 ** (bucket.failure_count - 4))
                bucket.lockout_until = now + delay
                return delay
            return 0

    def record_success(self, key: str = "global") -> None:
        """Mereset riwayat kegagalan setelah login berhasil."""
        with self._lock:
            self._buckets.pop(key, None)

    def reset(self) -> None:
        """Reset semua bucket untuk keperluan pengujian."""
        with self._lock:
            self._buckets.clear()


class SlidingWindowRateLimiter:
    """Rate limiter sliding-window per key/IP untuk proteksi spam & burst DDoS."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check_and_record(self, key: str = "global") -> tuple[bool, int]:
        """Mengembalikan (is_limited, retry_after_seconds)."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            if key not in self._hits and len(self._hits) >= _MAX_RATE_LIMIT_KEYS:
                stale = [k for k, dq in self._hits.items() if not dq or dq[-1] < cutoff]
                for k in stale:
                    del self._hits[k]
                while len(self._hits) >= _MAX_RATE_LIMIT_KEYS:
                    oldest_key = next(iter(self._hits))
                    del self._hits[oldest_key]

            dq = self._hits.setdefault(key, deque())
            while dq and dq[0] <= cutoff:
                dq.popleft()

            if len(dq) >= self.max_requests:
                retry_after = max(1, int(dq[0] + self.window_seconds - now + 0.99))
                return True, retry_after

            dq.append(now)
            return False, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


login_limiter = LoginRateLimiter(max_delay=30)
user_login_limiter = LoginRateLimiter(max_delay=30)
register_limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=600)
forgot_password_limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=900)
reset_password_limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=900)
public_consent_limiter = SlidingWindowRateLimiter(max_requests=30, window_seconds=600)
api_burst_limiter = SlidingWindowRateLimiter(max_requests=180, window_seconds=10)


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


def _resolve_jwt_secret() -> str:
    settings = get_settings()
    if settings.jwt_secret and len(settings.jwt_secret.strip()) >= 32:
        return settings.jwt_secret.strip()
    if settings.app_env == "test":
        return settings.jwt_secret or "dummy_secret_for_testing_purposes_only_32_chars"
    raise RuntimeError("JWT_SECRET must be configured (>= 32 chars) outside test mode")


def create_access_token(
    subject: str = "dashboard_user",
    expires_delta: Optional[timedelta] = None,
    role: str = "admin",
    user_id: Optional[int] = None,
) -> str:
    """Membuat token JWT HS256 dengan klaim role (admin/user) dan user_id opsional."""
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
    secret = _resolve_jwt_secret()
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_token(token: str) -> dict[str, Any]:
    """Memverifikasi token JWT secara ketat menolak algoritma selain HS256."""
    secret = _resolve_jwt_secret()
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
