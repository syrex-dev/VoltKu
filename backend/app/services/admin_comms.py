"""Layanan CRUD Admin & Pelanggan untuk Masukan/Bug, Broadcast Notifikasi, & Telegram."""

from __future__ import annotations

import json
import secrets
import time
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ChatLog, TelegramUser, User, UserFeedback, UserNotification
from app.services.app_config import get_app_config_map
from app.services.plans import resolve_user_plan
from app.services.push_notifier import create_and_dispatch_user_notification

FEEDBACK_CATEGORIES = ("feedback", "bug", "feature")
FEEDBACK_STATUSES = ("new", "reviewed", "resolved")
BROADCAST_CATEGORIES = ("announcement", "info", "promo", "maintenance", "support")
BROADCAST_SEVERITIES = ("info", "warning", "critical")
BROADCAST_TARGETS = ("all", "free", "pro", "user")


def serialize_feedback(row: UserFeedback) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "user_name": row.user_name_snapshot,
        "user_email": row.user_email_snapshot,
        "rating": int(row.rating),
        "category": row.category,
        "comment": row.comment or "",
        "status": row.status,
        "admin_reply": row.admin_reply or "",
        "replied_at": row.replied_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def create_user_feedback(
    session: Session,
    user: User,
    *,
    rating: int,
    category: str = "feedback",
    comment: Optional[str] = None,
) -> dict[str, Any]:
    clean_cat = (category or "feedback").strip().lower()
    if clean_cat not in FEEDBACK_CATEGORIES:
        raise ValueError("Kategori masukan harus 'feedback', 'bug', atau 'feature'.")
    if not (1 <= int(rating) <= 5):
        raise ValueError("Rating harus bernilai antara 1 hingga 5 bintang.")
    clean_comment = (comment or "").strip()
    if len(clean_comment) > 1000:
        raise ValueError("Komentar maksimal 1.000 karakter.")
    if clean_cat == "bug" and len(clean_comment) < 4:
        raise ValueError("Jelaskan detail kendala/bug minimal 4 karakter.")

    now_utc = int(time.time())
    row = UserFeedback(
        user_id=user.id,
        user_name_snapshot=(user.name or user.email or "Pengguna")[:128],
        user_email_snapshot=(user.email or "")[:128] or None,
        rating=int(rating),
        category=clean_cat,
        comment=clean_comment or None,
        status="new",
        admin_reply=None,
        replied_at=None,
        created_at=now_utc,
        updated_at=now_utc,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return serialize_feedback(row)


def list_user_feedback_history(
    session: Session,
    *,
    user_id: int,
    limit: int = 20,
) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(UserFeedback)
        .where(UserFeedback.user_id == int(user_id))
        .order_by(UserFeedback.created_at.desc(), UserFeedback.id.desc())
        .limit(limit)
    ).all()
    return [serialize_feedback(r) for r in rows]


def list_admin_feedback(
    session: Session,
    *,
    status_filter: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100,
) -> dict[str, Any]:
    if status_filter and status_filter not in FEEDBACK_STATUSES:
        raise ValueError("Status filter masukan tidak valid.")
    if category and category not in FEEDBACK_CATEGORIES:
        raise ValueError("Kategori filter masukan tidak valid.")

    all_rows = session.scalars(
        select(UserFeedback).order_by(UserFeedback.created_at.desc(), UserFeedback.id.desc())
    ).all()

    counts = {
        "total": len(all_rows),
        "new": sum(1 for r in all_rows if r.status == "new"),
        "reviewed": sum(1 for r in all_rows if r.status == "reviewed"),
        "resolved": sum(1 for r in all_rows if r.status == "resolved"),
    }

    filtered = [
        r
        for r in all_rows
        if (not status_filter or r.status == status_filter)
        and (not category or r.category == category)
    ][:limit]

    return {
        "items": [serialize_feedback(r) for r in filtered],
        "counts": counts,
    }


def update_admin_feedback(
    session: Session,
    feedback_id: int,
    *,
    new_status: Optional[str] = None,
    admin_reply: Optional[str] = None,
    reply_provided: bool = False,
    notify_user: bool = False,
) -> dict[str, Any]:
    row = session.get(UserFeedback, feedback_id)
    if not row:
        raise LookupError("Masukan atau laporan tidak ditemukan.")

    now_utc = int(time.time())
    if new_status is not None:
        clean_status = new_status.strip().lower()
        if clean_status not in FEEDBACK_STATUSES:
            raise ValueError("Status harus 'new', 'reviewed', atau 'resolved'.")
        row.status = clean_status

    if reply_provided:
        clean_reply = (admin_reply or "").strip()
        if len(clean_reply) > 1000:
            raise ValueError("Balasan admin maksimal 1.000 karakter.")
        row.admin_reply = clean_reply or None
        row.replied_at = now_utc if clean_reply else None

    row.updated_at = now_utc
    session.commit()
    session.refresh(row)

    if notify_user and row.user_id and row.admin_reply:
        create_and_dispatch_user_notification(
            session,
            user_id=int(row.user_id),
            title="Balasan Admin atas Masukan Anda",
            body=row.admin_reply,
            category="support",
            severity="info",
            data={"source": "admin_support", "feedback_id": row.id},
            event_key=f"fb-reply-{row.id}-{now_utc}",
            now_ts=now_utc,
            send_push=True,
        )

    return serialize_feedback(row)


def delete_admin_feedback(session: Session, feedback_id: int) -> dict[str, Any]:
    row = session.get(UserFeedback, feedback_id)
    if not row:
        raise LookupError("Masukan atau laporan tidak ditemukan.")
    session.delete(row)
    session.commit()
    return {"deleted": True, "id": feedback_id}


def _parse_notif_data(raw: Optional[str]) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def list_admin_notifications(session: Session, *, limit: int = 120) -> dict[str, Any]:
    """Mengambil daftar siaran notifikasi admin (terkelompok per batch & detail item)."""
    rows = session.scalars(
        select(UserNotification)
        .order_by(UserNotification.created_at.desc(), UserNotification.id.desc())
        .limit(500)
    ).all()

    user_ids = {int(r.user_id) for r in rows}
    users_map = (
        {u.id: u for u in session.scalars(select(User).where(User.id.in_(user_ids))).all()}
        if user_ids
        else {}
    )

    batches_map: dict[str, dict[str, Any]] = {}
    recent_items: list[dict[str, Any]] = []

    for r in rows:
        meta = _parse_notif_data(r.data_json)
        if meta.get("source") not in ("admin_broadcast", "admin_support"):
            continue
        batch_key = str(meta.get("batch_key") or f"single-{r.id}")
        user_obj = users_map.get(int(r.user_id))
        if len(recent_items) < limit:
            recent_items.append(
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "user_name": user_obj.name if user_obj else f"User #{r.user_id}",
                    "user_email": user_obj.email if user_obj else None,
                    "title": r.title,
                    "body": r.body,
                    "category": r.category,
                    "severity": r.severity,
                    "batch_key": batch_key,
                    "target": meta.get("target") or "user",
                    "is_read": bool(r.is_read),
                    "pushed_fcm": bool(r.pushed_fcm),
                    "created_at": r.created_at,
                }
            )

        bucket = batches_map.get(batch_key)
        if not bucket:
            bucket = {
                "batch_key": batch_key,
                "title": r.title,
                "body": r.body,
                "category": r.category,
                "severity": r.severity,
                "target": meta.get("target") or "user",
                "recipient_count": 0,
                "read_count": 0,
                "pushed_count": 0,
                "created_at": r.created_at,
            }
            batches_map[batch_key] = bucket
        bucket["recipient_count"] += 1
        if r.is_read:
            bucket["read_count"] += 1
        if r.pushed_fcm:
            bucket["pushed_count"] += 1

    batches = sorted(batches_map.values(), key=lambda x: x["created_at"], reverse=True)[:50]
    return {"batches": batches, "recent_items": recent_items}


def broadcast_admin_notification(
    session: Session,
    *,
    title: str,
    body: str,
    category: str = "announcement",
    severity: str = "info",
    target: str = "all",
    target_user_id: Optional[int] = None,
    send_push: bool = True,
) -> dict[str, Any]:
    clean_title = (title or "").strip()
    clean_body = (body or "").strip()
    if len(clean_title) < 2 or len(clean_title) > 160:
        raise ValueError("Judul notifikasi harus antara 2 hingga 160 karakter.")
    if len(clean_body) < 2 or len(clean_body) > 2000:
        raise ValueError("Isi pesan notifikasi harus antara 2 hingga 2.000 karakter.")

    clean_cat = (category or "announcement").strip().lower()
    if clean_cat not in BROADCAST_CATEGORIES:
        raise ValueError("Kategori notifikasi tidak valid.")
    clean_sev = (severity or "info").strip().lower()
    if clean_sev not in BROADCAST_SEVERITIES:
        raise ValueError("Tingkat severity harus 'info', 'warning', atau 'critical'.")
    clean_target = (target or "all").strip().lower()
    if clean_target not in BROADCAST_TARGETS:
        raise ValueError("Target penerima harus 'all', 'free', 'pro', atau 'user'.")

    recipients: list[User] = []
    if clean_target == "user":
        if not target_user_id:
            raise ValueError("Pilih akun pengguna tujuan terlebih dahulu.")
        target_u = session.get(User, int(target_user_id))
        if not target_u:
            raise LookupError("Akun pengguna target tidak ditemukan.")
        recipients = [target_u]
    else:
        active_users = session.scalars(select(User).where(User.is_active == 1)).all()
        if clean_target == "all":
            recipients = active_users
        else:
            cfg_map = get_app_config_map(session)
            for u in active_users:
                plan_info = resolve_user_plan(session, u, cfg_map)
                is_pro = bool(plan_info.get("is_pro"))
                if (clean_target == "pro" and is_pro) or (clean_target == "free" and not is_pro):
                    recipients.append(u)

    if not recipients:
        raise ValueError("Tidak ada pengguna aktif yang sesuai dengan target pilihan.")

    now_utc = int(time.time())
    batch_key = f"adm-{now_utc}-{secrets.token_hex(3)}"
    sent_count = 0
    pushed_count = 0

    for u in recipients:
        notif = create_and_dispatch_user_notification(
            session,
            user_id=int(u.id),
            title=clean_title,
            body=clean_body,
            category=clean_cat,
            severity=clean_sev,
            data={
                "source": "admin_broadcast",
                "batch_key": batch_key,
                "target": clean_target,
            },
            event_key=f"{batch_key}:{u.id}",
            now_ts=now_utc,
            send_push=bool(send_push),
        )
        if notif:
            sent_count += 1
            if notif.pushed_fcm:
                pushed_count += 1

    return {
        "batch_key": batch_key,
        "target": clean_target,
        "recipient_count": sent_count,
        "pushed_count": pushed_count,
        "created_at": now_utc,
    }


def delete_admin_notifications(
    session: Session,
    *,
    notification_id: Optional[int] = None,
    batch_key: Optional[str] = None,
) -> dict[str, Any]:
    if notification_id is not None:
        row = session.get(UserNotification, int(notification_id))
        if not row:
            raise LookupError("Notifikasi tidak ditemukan.")
        session.delete(row)
        session.commit()
        return {"deleted": 1}

    clean_batch = (batch_key or "").strip()
    if not clean_batch:
        raise ValueError("Sertakan ID notifikasi atau batch_key untuk menghapus.")

    rows = session.scalars(select(UserNotification)).all()
    matching_ids = [
        r.id for r in rows if _parse_notif_data(r.data_json).get("batch_key") == clean_batch
    ]
    if not matching_ids:
        raise LookupError("Gelombang broadcast notifikasi tidak ditemukan.")

    res = session.execute(
        delete(UserNotification).where(UserNotification.id.in_(matching_ids))
    )
    session.commit()
    return {"deleted": int(res.rowcount or 0), "batch_key": clean_batch}


def list_admin_telegram_users(
    session: Session,
    *,
    chat_log_limit: int = 20,
) -> dict[str, Any]:
    settings = get_settings()
    rows = session.scalars(
        select(TelegramUser).order_by(TelegramUser.name.asc(), TelegramUser.chat_id.asc())
    ).all()
    logs = session.scalars(
        select(ChatLog).order_by(ChatLog.ts.desc(), ChatLog.id.desc()).limit(chat_log_limit)
    ).all()
    names_by_cid = {int(r.chat_id): r.name for r in rows}

    return {
        "bot_configured": bool((settings.telegram_bot_token or "").strip()),
        "items": [
            {"chat_id": int(r.chat_id), "name": r.name}
            for r in rows
        ],
        "recent_logs": [
            {
                "id": log.id,
                "chat_id": int(log.chat_id),
                "sender_name": names_by_cid.get(int(log.chat_id), f"Chat {log.chat_id}"),
                "ts": log.ts,
                "question": log.question,
                "tools_used": log.tools_used,
                "tokens": int(log.tokens or 0),
            }
            for log in logs
        ],
    }


def create_admin_telegram_user(session: Session, *, chat_id: int, name: str) -> dict[str, Any]:
    if int(chat_id) == 0:
        raise ValueError("chat_id Telegram tidak boleh 0.")
    clean_name = (name or "").strip()
    if len(clean_name) < 2 or len(clean_name) > 128:
        raise ValueError("Nama penerima Telegram harus antara 2 hingga 128 karakter.")

    existing = session.get(TelegramUser, int(chat_id))
    if existing:
        raise FileExistsError(f"chat_id {chat_id} sudah terdaftar di allowlist Telegram.")

    row = TelegramUser(chat_id=int(chat_id), name=clean_name)
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"chat_id": int(row.chat_id), "name": row.name}


def update_admin_telegram_user(session: Session, *, chat_id: int, name: str) -> dict[str, Any]:
    row = session.get(TelegramUser, int(chat_id))
    if not row:
        raise LookupError("Penerima Telegram tidak ditemukan.")
    clean_name = (name or "").strip()
    if len(clean_name) < 2 or len(clean_name) > 128:
        raise ValueError("Nama penerima Telegram harus antara 2 hingga 128 karakter.")
    row.name = clean_name
    session.commit()
    session.refresh(row)
    return {"chat_id": int(row.chat_id), "name": row.name}


def delete_admin_telegram_user(session: Session, *, chat_id: int) -> dict[str, Any]:
    row = session.get(TelegramUser, int(chat_id))
    if not row:
        raise LookupError("Penerima Telegram tidak ditemukan.")
    session.delete(row)
    session.commit()
    return {"deleted": True, "chat_id": int(chat_id)}
