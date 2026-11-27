"""Endpoint REST API untuk registrasi token push & inbox notifikasi pengguna."""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import PushToken, UserNotification

router = APIRouter(prefix="/api/users", tags=["Notifications"])

ALLOWED_PLATFORMS = {"android", "ios", "web"}


class PushTokenRegisterRequest(BaseModel):
    token: str
    platform: str = "android"
    device_label: Optional[str] = None


class PushTokenDeleteRequest(BaseModel):
    token: str


class MarkNotificationsReadRequest(BaseModel):
    notification_id: Optional[int] = None
    notification_ids: Optional[list[int]] = None


def _notif_err(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail={"error": {"code": code, "message": message}})


def _require_user_id(current_user: dict[str, Any]) -> int:
    uid = current_user.get("user_id")
    if not uid:
        raise _notif_err(
            status.HTTP_403_FORBIDDEN,
            "Endpoint notifikasi hanya berlaku untuk akun pengguna terdaftar.",
        )
    return int(uid)


def _serialize_notification(item: UserNotification) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if item.data_json:
        try:
            parsed = json.loads(item.data_json)
            if isinstance(parsed, dict):
                data = parsed
        except Exception:
            data = {}
    return {
        "id": item.id,
        "device_id": item.device_id,
        "title": item.title,
        "body": item.body,
        "category": item.category,
        "severity": item.severity,
        "data": data,
        "is_read": bool(item.is_read),
        "pushed_fcm": bool(item.pushed_fcm),
        "created_at": item.created_at,
    }


@router.post("/push-token")
def register_push_token(
    req: PushTokenRegisterRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Mendaftarkan / memperbarui token perangkat untuk push notification (FCM)."""
    user_id = _require_user_id(current_user)
    clean_token = (req.token or "").strip()
    if len(clean_token) < 12 or len(clean_token) > 512:
        raise _notif_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Format push token tidak valid.",
        )

    platform = (req.platform or "android").strip().lower()
    if platform not in ALLOWED_PLATFORMS:
        raise _notif_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Platform harus 'android', 'ios', atau 'web'.",
        )

    clean_label = (
        req.device_label.strip()[:128]
        if req.device_label and req.device_label.strip()
        else None
    )
    now = int(time.time())

    existing = session.scalar(select(PushToken).where(PushToken.token == clean_token))
    if existing:
        existing.user_id = user_id
        existing.platform = platform
        if clean_label is not None:
            existing.device_label = clean_label
        existing.is_active = 1
        existing.updated_at = now
        session.commit()
        session.refresh(existing)
        return {"status": "updated", "token_id": existing.id, "platform": existing.platform}

    pt = PushToken(
        user_id=user_id,
        token=clean_token,
        platform=platform,
        device_label=clean_label,
        is_active=1,
        created_at=now,
        updated_at=now,
    )
    session.add(pt)
    session.commit()
    session.refresh(pt)
    return {"status": "registered", "token_id": pt.id, "platform": pt.platform}


@router.delete("/push-token")
def unregister_push_token(
    token: Optional[str] = Query(default=None),
    req: Optional[PushTokenDeleteRequest] = None,
    current_user: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Menonaktifkan push token saat pengguna logout dari aplikasi."""
    user_id = _require_user_id(current_user)
    raw_token = (token or (req.token if req else "") or "").strip()
    if not raw_token:
        raise _notif_err(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Parameter token wajib diisi.",
        )

    existing = session.scalar(
        select(PushToken).where(PushToken.token == raw_token, PushToken.user_id == user_id)
    )
    if not existing:
        return {"status": "not_found", "deactivated": False}

    existing.is_active = 0
    existing.updated_at = int(time.time())
    session.commit()
    return {"status": "deactivated", "deactivated": True}


@router.get("/notifications")
def list_user_notifications(
    since_id: int = Query(default=0, ge=0),
    unread_only: bool = Query(default=False),
    limit: int = Query(default=30, ge=1, le=100),
    current_user: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Mengambil daftar notifikasi milik pengguna yang login (juga dipakai WorkManager APK)."""
    user_id = _require_user_id(current_user)

    stmt = select(UserNotification).where(UserNotification.user_id == user_id)
    if since_id > 0:
        stmt = stmt.where(UserNotification.id > since_id).order_by(UserNotification.id.asc())
    else:
        stmt = stmt.order_by(UserNotification.id.desc())

    if unread_only:
        stmt = stmt.where(UserNotification.is_read == 0)

    items = session.scalars(stmt.limit(limit)).all()

    unread_count = session.scalar(
        select(func.count(UserNotification.id)).where(
            UserNotification.user_id == user_id,
            UserNotification.is_read == 0,
        )
    ) or 0

    latest_id = session.scalar(
        select(func.max(UserNotification.id)).where(UserNotification.user_id == user_id)
    ) or 0

    return {
        "items": [_serialize_notification(row) for row in items],
        "unread_count": int(unread_count),
        "latest_id": int(latest_id),
    }


@router.post("/notifications/read")
def mark_notifications_read(
    req: Optional[MarkNotificationsReadRequest] = None,
    current_user: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Menandai satu, beberapa, atau seluruh notifikasi pengguna sebagai sudah dibaca."""
    user_id = _require_user_id(current_user)
    target_ids: list[int] = []
    if req:
        if req.notification_id is not None:
            target_ids.append(int(req.notification_id))
        if req.notification_ids:
            target_ids.extend(int(nid) for nid in req.notification_ids)

    stmt = (
        update(UserNotification)
        .where(UserNotification.user_id == user_id, UserNotification.is_read == 0)
        .values(is_read=1)
    )
    if target_ids:
        stmt = stmt.where(UserNotification.id.in_(target_ids))

    res = session.execute(stmt)
    session.commit()
    return {"updated": int(res.rowcount or 0)}
