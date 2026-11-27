"""Layanan notifikasi native Android (FCM HTTP v1 + antrean inbox DB untuk fallback)."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Optional

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Device, PushToken, UserNotification

logger = logging.getLogger(__name__)

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
DEFAULT_ANDROID_CHANNEL_ID = "voltku_alerts"

# Cache sederhana token OAuth2 Firebase di memori proses
_cached_token: dict[str, Any] = {"access_token": None, "expires_at": 0, "project_id": None}
_cached_sa_data: dict[str, Any] = {"path": None, "data": None}

# Hook opsional untuk pengujian terisolasi tanpa memanggil network Google/FCM
FcmSenderFn = Callable[[str, str, str, dict[str, str]], tuple[bool, bool]]
_custom_fcm_sender: Optional[FcmSenderFn] = None


def set_custom_fcm_sender(sender: Optional[FcmSenderFn]) -> None:
    """Memasang atau menghapus custom sender FCM (khusus unit test)."""
    global _custom_fcm_sender
    _custom_fcm_sender = sender


def reset_fcm_caches() -> None:
    """Mengosongkan cache token OAuth2 & file service account Firebase."""
    _cached_token.update({"access_token": None, "expires_at": 0, "project_id": None})
    _cached_sa_data.update({"path": None, "data": None})


def _load_service_account() -> Optional[dict[str, Any]]:
    settings = get_settings()
    cred_path = (settings.firebase_credentials_path or "").strip()
    if not cred_path:
        return None
    if _cached_sa_data["path"] == cred_path and _cached_sa_data["data"]:
        return _cached_sa_data["data"]
    file_path = Path(cred_path)
    if not file_path.is_file():
        logger.warning("File kredensial Firebase tidak ditemukan di: %s", cred_path)
        return None
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if not data.get("client_email") or not data.get("private_key"):
            logger.warning(
                "Format service account Firebase tidak lengkap (client_email/private_key)"
            )
            return None
        _cached_sa_data["path"] = cred_path
        _cached_sa_data["data"] = data
        return data
    except Exception as exc:
        logger.error("Gagal membaca service account Firebase: %s", exc)
        return None


def _get_fcm_access_token_and_project() -> tuple[Optional[str], Optional[str]]:
    """Memperoleh OAuth2 Bearer Token untuk FCM HTTP v1 memakai RS256 JWT assertion."""
    now = int(time.time())
    settings = get_settings()
    if (
        _cached_token.get("access_token")
        and _cached_token.get("expires_at", 0) > now + 60
        and _cached_token.get("project_id")
    ):
        return _cached_token["access_token"], _cached_token["project_id"]

    sa = _load_service_account()
    if not sa:
        return None, None

    project_id = (settings.firebase_project_id or sa.get("project_id") or "").strip()
    if not project_id:
        logger.warning("firebase_project_id belum dikonfigurasi.")
        return None, None

    token_uri = sa.get("token_uri") or GOOGLE_TOKEN_URI
    payload = {
        "iss": sa["client_email"],
        "scope": FCM_SCOPE,
        "aud": token_uri,
        "iat": now,
        "exp": now + 3600,
    }
    try:
        assertion = jwt.encode(payload, sa["private_key"], algorithm="RS256")
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(
                token_uri,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
                },
            )
            resp.raise_for_status()
            body = resp.json()
        access_token = body.get("access_token")
        expires_in = int(body.get("expires_in", 3600))
        if access_token:
            _cached_token["access_token"] = access_token
            _cached_token["expires_at"] = now + expires_in
            _cached_token["project_id"] = project_id
            return access_token, project_id
    except Exception as exc:
        logger.warning("Gagal mengambil OAuth2 token FCM: %s", exc)
    return None, None


def is_fcm_configured() -> bool:
    """True jika stub uji terpasang atau service account Firebase siap dipakai."""
    if _custom_fcm_sender is not None:
        return True
    settings = get_settings()
    if settings.app_env == "test":
        return False
    return _load_service_account() is not None


def _send_fcm_http_v1(
    token: str,
    title: str,
    body: str,
    data: dict[str, str],
) -> tuple[bool, bool]:
    """Mengirim 1 pesan via FCM HTTP v1.

    Mengembalikan (delivered: bool, should_deactivate_token: bool).
    """
    if _custom_fcm_sender is not None:
        return _custom_fcm_sender(token, title, body, data)

    settings = get_settings()
    if settings.app_env == "test":
        return False, False

    access_token, project_id = _get_fcm_access_token_and_project()
    if not access_token or not project_id:
        return False, False

    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    message_payload = {
        "message": {
            "token": token,
            "notification": {
                "title": title,
                "body": body,
            },
            "data": data,
            "android": {
                "priority": "HIGH",
                "notification": {
                    "channel_id": DEFAULT_ANDROID_CHANNEL_ID,
                    "sound": "default",
                    "notification_priority": "PRIORITY_MAX",
                    "visibility": "PUBLIC",
                },
            },
        }
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.post(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=message_payload,
            )
        if resp.status_code == 200:
            return True, False

        err_text = resp.text[:400]
        err_markers = ("UNREGISTERED", "INVALID_ARGUMENT", "Requested entity was not found")
        if resp.status_code in (400, 404) and any(m in err_text for m in err_markers):
            logger.info("FCM token tidak lagi valid (%d), menonaktifkan token.", resp.status_code)
            return False, True

        logger.warning("Gagal kirim FCM HTTP %d: %s", resp.status_code, err_text)
        return False, False
    except Exception as exc:
        logger.warning("Kesalahan jaringan saat kirim FCM: %s", exc)
        return False, False


def _serialize_data_for_fcm(data: Optional[dict[str, Any]]) -> dict[str, str]:
    if not data:
        return {}
    return {str(k): str(v) for k, v in data.items() if v is not None}


def create_and_dispatch_user_notification(
    session: Session,
    *,
    user_id: int,
    title: str,
    body: str,
    category: str = "alert",
    severity: str = "warning",
    device_id: Optional[str] = None,
    data: Optional[dict[str, Any]] = None,
    event_key: Optional[str] = None,
    now_ts: Optional[int] = None,
    send_push: bool = True,
) -> Optional[UserNotification]:
    """Menyimpan notifikasi ke inbox user & mengirim push FCM ke semua token aktif user tersebut."""
    if not user_id:
        return None

    clean_key = event_key.strip()[:128] if event_key else None
    if clean_key:
        existing = session.scalar(
            select(UserNotification).where(UserNotification.event_key == clean_key)
        )
        if existing is not None:
            return existing

    ts = int(now_ts if now_ts is not None else time.time())
    payload_data = dict(data or {})
    if device_id and "device_id" not in payload_data:
        payload_data["device_id"] = device_id
    payload_data.setdefault("category", category)
    payload_data.setdefault("severity", severity)

    notif = UserNotification(
        user_id=user_id,
        device_id=device_id,
        title=title.strip()[:160],
        body=body.strip(),
        category=category,
        severity=severity,
        data_json=json.dumps(payload_data, ensure_ascii=False),
        event_key=clean_key,
        is_read=0,
        pushed_fcm=0,
        created_at=ts,
    )
    session.add(notif)
    session.flush()

    fcm_data = _serialize_data_for_fcm({**payload_data, "notification_id": notif.id})
    active_tokens = session.scalars(
        select(PushToken).where(PushToken.user_id == user_id, PushToken.is_active == 1)
    ).all()

    any_pushed = False
    if send_push and active_tokens and is_fcm_configured():
        for pt in active_tokens:
            delivered, deactivate = _send_fcm_http_v1(
                token=pt.token,
                title=notif.title,
                body=notif.body,
                data=fcm_data,
            )
            if delivered:
                any_pushed = True
            if deactivate:
                pt.is_active = 0
                pt.updated_at = ts
        if any_pushed:
            notif.pushed_fcm = 1

    session.commit()
    session.refresh(notif)
    return notif


def notify_device_owner(
    session: Session,
    *,
    device: Device,
    title: str,
    body: str,
    category: str = "alert",
    severity: str = "warning",
    data: Optional[dict[str, Any]] = None,
    event_key: Optional[str] = None,
    now_ts: Optional[int] = None,
) -> Optional[UserNotification]:
    """Mengirim notifikasi ke pemilik perangkat bila device terikat ke akun user."""
    owner_id = getattr(device, "owner_user_id", None)
    if not owner_id:
        return None
    return create_and_dispatch_user_notification(
        session,
        user_id=int(owner_id),
        title=title,
        body=body,
        category=category,
        severity=severity,
        device_id=device.id,
        data=data,
        event_key=event_key,
        now_ts=now_ts,
    )
