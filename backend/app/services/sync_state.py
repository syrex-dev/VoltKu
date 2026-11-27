"""Layanan state & revisi sinkronisasi ringan berbasis DB untuk Admin dan Publik."""

import hashlib
import time
from typing import Any, Optional

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import (
    Anomaly,
    AppConfig,
    Device,
    DiscountCode,
    PaymentMethod,
    Setting,
    SubscriptionPlan,
    TelegramUser,
    TermsConsent,
    UpgradeRequest,
    User,
    UserFeedback,
    UserNotification,
    UserSetting,
)
from app.services.app_config import is_public_read_enabled
from app.services.payments import expire_stale_awaiting_requests


def _digest_parts(*parts: Any) -> str:
    payload = "|".join(str(p) for p in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _serialize_upgrade_brief(
    row: UpgradeRequest,
    user_name: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "id": row.id,
        "order_code": row.order_code,
        "status": row.status,
        "requested_tier": row.requested_tier,
        "plan_name": row.plan_name_snapshot or (row.requested_tier or "pro").upper(),
        "amount_rp": int(row.amount_rp or 0),
        "user_name": user_name or f"User #{row.user_id}",
        "created_at": row.created_at,
        "submitted_at": row.submitted_at,
        "resolved_at": row.resolved_at,
    }


def compute_public_sync_state(session: Session, now_ts: Optional[int] = None) -> dict[str, Any]:
    """Menghasilkan fingerprint revisi ringan untuk konfigurasi publik, paket & metode bayar."""
    now_epoch = now_ts if now_ts is not None else int(time.time())

    cfg_rows = session.execute(
        select(AppConfig.key, AppConfig.value, AppConfig.updated_at).order_by(AppConfig.key.asc())
    ).all()
    config_rev = _digest_parts(
        *[
            f"{k}:{updated}:{hashlib.sha256(v.encode('utf-8')).hexdigest()[:8]}"
            for k, v, updated in cfg_rows
        ]
    )

    plan_rows = session.execute(
        select(
            SubscriptionPlan.id,
            SubscriptionPlan.slug,
            SubscriptionPlan.name,
            SubscriptionPlan.price_monthly_rp,
            SubscriptionPlan.price_yearly_rp,
            SubscriptionPlan.promo_discount_type,
            SubscriptionPlan.promo_discount_value,
            SubscriptionPlan.promo_label,
            SubscriptionPlan.promo_starts_at,
            SubscriptionPlan.promo_expires_at,
            SubscriptionPlan.max_devices,
            SubscriptionPlan.history_days,
            SubscriptionPlan.forecast_enabled,
            SubscriptionPlan.export_enabled,
            SubscriptionPlan.anomaly_advanced,
            SubscriptionPlan.features_json,
            SubscriptionPlan.badge_text,
            SubscriptionPlan.is_recommended,
            SubscriptionPlan.is_active,
            SubscriptionPlan.sort_order,
            SubscriptionPlan.updated_at,
        ).order_by(SubscriptionPlan.id.asc())
    ).all()
    plan_tokens = []
    for p in plan_rows:
        promo_start_ok = p[8] is None or p[8] <= now_epoch
        promo_end_ok = p[9] is None or p[9] > now_epoch
        promo_live = 1 if (promo_start_ok and promo_end_ok) else 0
        plan_tokens.append(f"{':'.join(str(x) for x in p)}:{promo_live}")
    plans_rev = _digest_parts(*plan_tokens)

    pm_rows = session.execute(
        select(
            PaymentMethod.id,
            PaymentMethod.type,
            PaymentMethod.label,
            PaymentMethod.account_number,
            PaymentMethod.account_holder,
            PaymentMethod.qris_image_path,
            PaymentMethod.instructions,
            PaymentMethod.is_active,
            PaymentMethod.sort_order,
        ).order_by(PaymentMethod.id.asc())
    ).all()
    methods_rev = _digest_parts(*[":".join(str(x) for x in m) for m in pm_rows])

    public_read = is_public_read_enabled(session)
    combined_rev = _digest_parts(config_rev, plans_rev, methods_rev, "1" if public_read else "0")

    return {
        "rev": combined_rev,
        "config_rev": config_rev,
        "plans_rev": plans_rev,
        "payment_methods_rev": methods_rev,
        "public_read_enabled": public_read,
        "server_ts": now_epoch,
    }


def compute_user_sync_state(
    session: Session, user_id: int, now_ts: Optional[int] = None
) -> dict[str, Any]:
    """Menghasilkan status sinkronisasi milik tenant tertentu + revisi publik."""
    now_epoch = now_ts if now_ts is not None else int(time.time())
    if expire_stale_awaiting_requests(session, user_id=int(user_id), now_utc=now_epoch):
        session.commit()

    user = session.get(User, int(user_id))
    user_sig = ""
    if user:
        plan_expired = bool(user.plan_expires_at and user.plan_expires_at <= now_epoch)
        user_sig = ":".join(
            str(x)
            for x in (
                user.id,
                user.name,
                user.plan_tier,
                user.plan_id,
                user.plan_expires_at,
                user.plan_updated_at,
                user.is_active,
                "1" if plan_expired else "0",
            )
        )

    req_rows = session.scalars(
        select(UpgradeRequest)
        .where(UpgradeRequest.user_id == int(user_id))
        .order_by(UpgradeRequest.created_at.desc(), UpgradeRequest.id.desc())
        .limit(20)
    ).all()
    req_sig = ":".join(
        f"{r.id}/{r.status}/{r.submitted_at}/{r.resolved_at}/{r.expires_at}/{r.amount_rp}"
        for r in req_rows
    )

    dev_rows = session.execute(
        select(
            Device.id,
            Device.name,
            Device.location,
            Device.mcb_watt,
            Device.status,
            Device.is_public_demo,
        )
        .where(Device.owner_user_id == int(user_id))
        .order_by(Device.id.asc())
    ).all()
    dev_sig = ":".join("|".join(str(x) for x in d) for d in dev_rows)

    us_rows = session.execute(
        select(UserSetting.key, UserSetting.value)
        .where(UserSetting.user_id == int(user_id))
        .order_by(UserSetting.key.asc())
    ).all()
    us_sig = ":".join(f"{k}={v}" for k, v in us_rows)

    unread_count = int(
        session.scalar(
            select(func.count(UserNotification.id)).where(
                UserNotification.user_id == int(user_id),
                UserNotification.is_read == 0,
            )
        )
        or 0
    )
    latest_notif_id = int(
        session.scalar(
            select(func.max(UserNotification.id)).where(UserNotification.user_id == int(user_id))
        )
        or 0
    )

    public_state = compute_public_sync_state(session, now_ts=now_epoch)
    user_rev = _digest_parts(user_sig, req_sig, dev_sig, us_sig)
    inbox_rev = _digest_parts(unread_count, latest_notif_id)

    latest_upgrade_dict = (
        _serialize_upgrade_brief(req_rows[0], user_name=user.name if user else None)
        if req_rows
        else None
    )

    return {
        "rev": _digest_parts(user_rev, inbox_rev, public_state["rev"]),
        "user_rev": user_rev,
        "inbox_rev": inbox_rev,
        "public_rev": public_state["rev"],
        "plans_rev": public_state["plans_rev"],
        "payment_methods_rev": public_state["payment_methods_rev"],
        "public_read_enabled": public_state["public_read_enabled"],
        "unread_notifications": unread_count,
        "latest_upgrade": latest_upgrade_dict,
        "server_ts": now_epoch,
    }


def compute_admin_sync_state(session: Session, now_ts: Optional[int] = None) -> dict[str, Any]:
    """Menghasilkan status & revisi sinkronisasi terpadu untuk Portal Admin."""
    now_epoch = now_ts if now_ts is not None else int(time.time())
    if expire_stale_awaiting_requests(session, now_utc=now_epoch):
        session.commit()

    user_rows = session.execute(
        select(
            User.id,
            User.name,
            User.email,
            User.is_active,
            User.plan_tier,
            User.plan_id,
            User.plan_expires_at,
            User.plan_updated_at,
            User.last_login_at,
        ).order_by(User.id.asc())
    ).all()
    user_names = {int(u[0]): str(u[1] or u[2] or f"User #{u[0]}") for u in user_rows}
    users_rev = _digest_parts(*[":".join(str(x) for x in u) for u in user_rows])

    device_rows = session.execute(
        select(
            Device.id,
            Device.name,
            Device.location,
            Device.mcb_watt,
            Device.owner_user_id,
            Device.is_public_demo,
            Device.status,
        ).order_by(Device.id.asc())
    ).all()
    devices_rev = _digest_parts(*[":".join(str(x) for x in d) for d in device_rows])

    anom_stats = session.execute(select(func.count(Anomaly.id), func.max(Anomaly.id))).one()
    anom_count = int(anom_stats[0] or 0)
    anom_max_id = int(anom_stats[1] or 0)
    anomalies_rev = _digest_parts(anom_count, anom_max_id)

    consent_stats = session.execute(
        select(func.count(TermsConsent.id), func.max(TermsConsent.id))
    ).one()
    consents_rev = _digest_parts(int(consent_stats[0] or 0), int(consent_stats[1] or 0))

    fb_stats = session.execute(
        select(
            func.count(UserFeedback.id),
            func.max(UserFeedback.updated_at),
            func.sum(case((UserFeedback.status == "new", 1), else_=0)),
        )
    ).one()
    fb_total = int(fb_stats[0] or 0)
    fb_max_upd = int(fb_stats[1] or 0)
    fb_new = int(fb_stats[2] or 0)
    feedback_rev = _digest_parts(fb_total, fb_max_upd, fb_new)

    tg_rows = session.execute(
        select(TelegramUser.chat_id, TelegramUser.name).order_by(TelegramUser.chat_id.asc())
    ).all()
    telegram_users_rev = _digest_parts(*[f"{cid}:{name}" for cid, name in tg_rows])

    discount_rows = session.execute(
        select(
            DiscountCode.id,
            DiscountCode.code,
            DiscountCode.label,
            DiscountCode.discount_type,
            DiscountCode.discount_value,
            DiscountCode.max_discount_rp,
            DiscountCode.min_purchase_rp,
            DiscountCode.target_plan_slug,
            DiscountCode.target_cycle,
            DiscountCode.max_uses,
            DiscountCode.used_count,
            DiscountCode.starts_at,
            DiscountCode.expires_at,
            DiscountCode.is_active,
            DiscountCode.updated_at,
        ).order_by(DiscountCode.id.asc())
    ).all()
    discounts_rev = _digest_parts(*[":".join(str(x) for x in dc) for dc in discount_rows])

    setting_rows = session.execute(
        select(Setting.key, Setting.value).order_by(Setting.key.asc())
    ).all()
    settings_rev = _digest_parts(*[f"{k}={v}" for k, v in setting_rows])

    upgrade_rows = session.scalars(
        select(UpgradeRequest)
        .order_by(UpgradeRequest.created_at.desc(), UpgradeRequest.id.desc())
        .limit(150)
    ).all()
    upgrades_rev = _digest_parts(
        *[
            f"{r.id}:{r.status}:{r.submitted_at}:{r.resolved_at}:{r.expires_at}:{r.amount_rp}"
            for r in upgrade_rows
        ]
    )

    verifying_rows = [r for r in upgrade_rows if r.status == "verifying"]
    awaiting_rows = [r for r in upgrade_rows if r.status == "awaiting_payment"]
    pending_rows = [r for r in upgrade_rows if r.status == "pending"]

    verifying_sorted = sorted(
        verifying_rows,
        key=lambda r: (r.submitted_at or r.created_at, r.id),
        reverse=True,
    )
    awaiting_sorted = sorted(
        awaiting_rows,
        key=lambda r: (r.created_at, r.id),
        reverse=True,
    )

    latest_verifying = (
        _serialize_upgrade_brief(
            verifying_sorted[0],
            user_names.get(int(verifying_sorted[0].user_id)),
        )
        if verifying_sorted
        else None
    )
    latest_awaiting = (
        _serialize_upgrade_brief(
            awaiting_sorted[0],
            user_names.get(int(awaiting_sorted[0].user_id)),
        )
        if awaiting_sorted
        else None
    )

    public_state = compute_public_sync_state(session, now_ts=now_epoch)
    admin_rev = _digest_parts(
        upgrades_rev,
        users_rev,
        devices_rev,
        anomalies_rev,
        discounts_rev,
        settings_rev,
        consents_rev,
        feedback_rev,
        telegram_users_rev,
        public_state["rev"],
    )

    return {
        "rev": admin_rev,
        "upgrades_rev": upgrades_rev,
        "users_rev": users_rev,
        "devices_rev": devices_rev,
        "anomalies_rev": anomalies_rev,
        "plans_rev": public_state["plans_rev"],
        "discounts_rev": discounts_rev,
        "payment_methods_rev": public_state["payment_methods_rev"],
        "settings_rev": settings_rev,
        "config_rev": public_state["config_rev"],
        "consents_rev": consents_rev,
        "feedback_rev": feedback_rev,
        "telegram_users_rev": telegram_users_rev,
        "public_read_enabled": public_state["public_read_enabled"],
        "counts": {
            "verifying": len(verifying_rows),
            "awaiting": len(awaiting_rows),
            "pending": len(pending_rows),
            "needs_action": len(verifying_rows) + len(pending_rows),
            "users": len(user_rows),
            "devices": len(device_rows),
            "anomalies": anom_count,
            "new_feedback": fb_new,
            "telegram_users": len(tg_rows),
        },
        "latest_verifying": latest_verifying,
        "latest_awaiting": latest_awaiting,
        "server_ts": now_epoch,
    }
