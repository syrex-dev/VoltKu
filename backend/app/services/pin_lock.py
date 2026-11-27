"""Layanan Kunci Aplikasi PIN 6 digit tersinkron lintas perangkat untuk akun pengguna."""

import re
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_user_password
from app.models import User, UserSetting

PIN_ENABLED_KEY = "app_pin_enabled"
PIN_HASH_KEY = "app_pin_hash"
PIN_UPDATED_AT_KEY = "app_pin_updated_at"
PIN_FAILED_KEY = "app_pin_failed_attempts"
PIN_LOCKED_UNTIL_KEY = "app_pin_locked_until"

PIN_ALL_KEYS = (
    PIN_ENABLED_KEY,
    PIN_HASH_KEY,
    PIN_UPDATED_AT_KEY,
    PIN_FAILED_KEY,
    PIN_LOCKED_UNTIL_KEY,
)

PIN_RE = re.compile(r"^\d{6}$")
WEAK_PINS = {
    "012345",
    "123456",
    "234567",
    "345678",
    "456789",
    "987654",
    "876543",
    "765432",
    "654321",
    "543210",
    "112233",
    "121212",
    "123123",
    "102030",
    "010101",
    "696969",
}
MAX_PIN_FAILS_BEFORE_LOCK = 5


def _pin_error(code: int, message: str, extra: Optional[dict[str, Any]] = None) -> HTTPException:
    payload: dict[str, Any] = {"code": code, "message": message}
    if extra:
        payload.update(extra)
    return HTTPException(status_code=code, detail={"error": payload})


def _get_pin_settings_map(session: Session, user_id: int) -> dict[str, str]:
    rows = session.scalars(
        select(UserSetting).where(
            UserSetting.user_id == int(user_id),
            UserSetting.key.in_(PIN_ALL_KEYS),
        )
    ).all()
    return {r.key: r.value for r in rows}


def _upsert_pin_setting(session: Session, user_id: int, key: str, value: str) -> None:
    existing = session.scalar(
        select(UserSetting).where(
            UserSetting.user_id == int(user_id),
            UserSetting.key == key,
        )
    )
    if existing:
        existing.value = value
    else:
        session.add(UserSetting(user_id=int(user_id), key=key, value=value))


def get_app_lock_metadata(
    session: Session, user_id: int, now_ts: Optional[int] = None
) -> dict[str, Any]:
    """Kembalikan metadata non-rahasia status PIN 6 digit pengguna untuk /api/users/me."""
    now_utc = now_ts if now_ts is not None else int(datetime.now(timezone.utc).timestamp())
    smap = _get_pin_settings_map(session, user_id)
    enabled = smap.get(PIN_ENABLED_KEY) == "1" and bool(smap.get(PIN_HASH_KEY))
    try:
        updated_at = int(smap.get(PIN_UPDATED_AT_KEY) or 0)
    except ValueError:
        updated_at = 0
    try:
        locked_until_raw = int(smap.get(PIN_LOCKED_UNTIL_KEY) or 0)
    except ValueError:
        locked_until_raw = 0
    locked_until = locked_until_raw if locked_until_raw > now_utc else None
    return {
        "pin_enabled": enabled,
        "pin_updated_at": updated_at,
        "locked_until": locked_until,
    }


def validate_pin_format(pin: str) -> str:
    """Validasi PIN tepat 6 digit dan bukan pola berulang/berurutan lemah."""
    clean = str(pin or "").strip()
    if not PIN_RE.match(clean):
        raise _pin_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PIN keamanan harus berupa tepat 6 angka.",
        )
    if len(set(clean)) == 1 or clean in WEAK_PINS:
        raise _pin_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PIN terlalu mudah ditebak (hindari angka sama atau berurutan seperti 123456).",
        )
    return clean


def _check_pin_lockout(
    smap: dict[str, str], now_utc: int
) -> Optional[int]:
    try:
        locked_until = int(smap.get(PIN_LOCKED_UNTIL_KEY) or 0)
    except ValueError:
        locked_until = 0
    if locked_until > now_utc:
        return locked_until - now_utc
    return None


def verify_user_pin(
    session: Session,
    user_id: int,
    pin: str,
    *,
    now_ts: Optional[int] = None,
) -> dict[str, Any]:
    """Verifikasi PIN 6 digit di server dengan lockout progresif anti brute-force."""
    now_utc = now_ts if now_ts is not None else int(datetime.now(timezone.utc).timestamp())
    smap = _get_pin_settings_map(session, user_id)
    enabled = smap.get(PIN_ENABLED_KEY) == "1" and bool(smap.get(PIN_HASH_KEY))
    if not enabled:
        return {
            "verified": True,
            "pin_enabled": False,
            "attempts": 0,
            "remaining_attempts": MAX_PIN_FAILS_BEFORE_LOCK,
            "locked_until": None,
            "retry_after": 0,
        }

    wait_sec = _check_pin_lockout(smap, now_utc)
    if wait_sec is not None:
        raise _pin_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Terlalu banyak percobaan PIN salah. Tunggu {wait_sec} detik lalu coba lagi.",
            extra={"retry_after": wait_sec, "locked_until": now_utc + wait_sec},
        )

    clean_pin = str(pin or "").strip()
    stored_hash = smap.get(PIN_HASH_KEY, "")
    if PIN_RE.match(clean_pin) and verify_user_password(clean_pin, stored_hash):
        _upsert_pin_setting(session, user_id, PIN_FAILED_KEY, "0")
        _upsert_pin_setting(session, user_id, PIN_LOCKED_UNTIL_KEY, "0")
        session.commit()
        return {
            "verified": True,
            "pin_enabled": True,
            "attempts": 0,
            "remaining_attempts": MAX_PIN_FAILS_BEFORE_LOCK,
            "locked_until": None,
            "retry_after": 0,
        }

    try:
        failed = int(smap.get(PIN_FAILED_KEY) or 0) + 1
    except ValueError:
        failed = 1

    locked_until: Optional[int] = None
    retry_after = 0
    if failed >= MAX_PIN_FAILS_BEFORE_LOCK:
        retry_after = min(300, 60 * (2 ** (failed - MAX_PIN_FAILS_BEFORE_LOCK)))
        locked_until = now_utc + retry_after
        _upsert_pin_setting(session, user_id, PIN_LOCKED_UNTIL_KEY, str(locked_until))

    _upsert_pin_setting(session, user_id, PIN_FAILED_KEY, str(failed))
    session.commit()

    return {
        "verified": False,
        "pin_enabled": True,
        "attempts": failed,
        "remaining_attempts": max(0, MAX_PIN_FAILS_BEFORE_LOCK - failed),
        "locked_until": locked_until,
        "retry_after": retry_after,
    }


def set_user_pin(
    session: Session,
    user_id: int,
    new_pin: str,
    *,
    current_pin: Optional[str] = None,
    now_ts: Optional[int] = None,
) -> dict[str, Any]:
    """Menyetel atau memperbarui PIN 6 digit akun dengan hashing PBKDF2-HMAC-SHA256."""
    now_utc = now_ts if now_ts is not None else int(datetime.now(timezone.utc).timestamp())
    smap = _get_pin_settings_map(session, user_id)
    already_enabled = smap.get(PIN_ENABLED_KEY) == "1" and bool(smap.get(PIN_HASH_KEY))

    if already_enabled:
        if not current_pin:
            raise _pin_error(
                status.HTTP_401_UNAUTHORIZED,
                "Masukkan PIN aktif saat ini terlebih dahulu untuk mengganti PIN.",
            )
        check = verify_user_pin(session, user_id, current_pin, now_ts=now_utc)
        if not check["verified"]:
            msg = (
                f"Terlalu banyak percobaan PIN salah. Tunggu {check['retry_after']} detik."
                if check["retry_after"] > 0
                else "PIN aktif saat ini tidak cocok."
            )
            code = (
                status.HTTP_429_TOO_MANY_REQUESTS
                if check["retry_after"] > 0
                else status.HTTP_401_UNAUTHORIZED
            )
            raise _pin_error(
                code,
                msg,
                extra={
                    "retry_after": check["retry_after"],
                    "locked_until": check["locked_until"],
                },
            )

    clean_new = validate_pin_format(new_pin)
    hashed = hash_password(clean_new)
    _upsert_pin_setting(session, user_id, PIN_ENABLED_KEY, "1")
    _upsert_pin_setting(session, user_id, PIN_HASH_KEY, hashed)
    _upsert_pin_setting(session, user_id, PIN_UPDATED_AT_KEY, str(now_utc))
    _upsert_pin_setting(session, user_id, PIN_FAILED_KEY, "0")
    _upsert_pin_setting(session, user_id, PIN_LOCKED_UNTIL_KEY, "0")
    session.commit()
    return get_app_lock_metadata(session, user_id, now_ts=now_utc)


def disable_user_pin(
    session: Session,
    user: User,
    *,
    current_pin: Optional[str] = None,
    account_password: Optional[str] = None,
    now_ts: Optional[int] = None,
) -> dict[str, Any]:
    """Menonaktifkan PIN aplikasi setelah memverifikasi PIN aktif atau kata sandi akun."""
    now_utc = now_ts if now_ts is not None else int(datetime.now(timezone.utc).timestamp())
    smap = _get_pin_settings_map(session, user.id)
    already_enabled = smap.get(PIN_ENABLED_KEY) == "1" and bool(smap.get(PIN_HASH_KEY))

    if already_enabled:
        authorized = False
        if current_pin:
            check = verify_user_pin(session, user.id, current_pin, now_ts=now_utc)
            if check["verified"]:
                authorized = True
            elif check["retry_after"] > 0:
                raise _pin_error(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    f"Terlalu banyak percobaan PIN salah. Tunggu {check['retry_after']} detik.",
                    extra={
                        "retry_after": check["retry_after"],
                        "locked_until": check["locked_until"],
                    },
                )
        elif account_password:
            has_local = not str(getattr(user, "password_hash", "") or "").startswith("!")
            if has_local and verify_user_password(account_password, user.password_hash):
                authorized = True

        if not authorized:
            raise _pin_error(
                status.HTTP_401_UNAUTHORIZED,
                "Verifikasi gagal. Masukkan PIN aktif atau kata sandi akun yang benar.",
            )

    _upsert_pin_setting(session, user.id, PIN_ENABLED_KEY, "0")
    _upsert_pin_setting(session, user.id, PIN_HASH_KEY, "")
    _upsert_pin_setting(session, user.id, PIN_UPDATED_AT_KEY, str(now_utc))
    _upsert_pin_setting(session, user.id, PIN_FAILED_KEY, "0")
    _upsert_pin_setting(session, user.id, PIN_LOCKED_UNTIL_KEY, "0")
    session.commit()
    return get_app_lock_metadata(session, user.id, now_ts=now_utc)

