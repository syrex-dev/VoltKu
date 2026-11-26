import time
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Device, UpgradeRequest, User

ACTIVE_UPGRADE_STATUSES = ("pending", "awaiting_payment", "verifying")


def _parse_bool(raw: Any, default: bool = False) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    s = str(raw).strip().lower()
    if not s:
        return default
    return s in ("true", "1", "yes", "on")


def _parse_int(raw: Any, default: int, min_val: int, max_val: int) -> int:
    try:
        val = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return max(min_val, min(max_val, val))


def get_freemium_config(cfg_map: dict[str, str]) -> dict[str, Any]:
    """Mengurai seluruh konfigurasi paket Freemium dari app_config."""
    freemium_enabled = _parse_bool(cfg_map.get("freemium_enabled"), True)
    free_name = (cfg_map.get("free_plan_name") or "").strip() or "VoltKu Gratis"
    pro_name = (cfg_map.get("pro_plan_name") or "").strip() or "VoltKu Pro"

    return {
        "freemium_enabled": freemium_enabled,
        "free_plan_name": free_name,
        "free_max_devices": _parse_int(cfg_map.get("free_max_devices"), 1, 1, 100),
        "free_history_days": _parse_int(cfg_map.get("free_history_days"), 3, 1, 366),
        "free_forecast_enabled": _parse_bool(cfg_map.get("free_forecast_enabled"), False),
        "free_export_enabled": _parse_bool(cfg_map.get("free_export_enabled"), False),
        "pro_plan_name": pro_name,
        "pro_monthly_price_rp": _parse_int(
            cfg_map.get("pro_monthly_price_rp"), 30000, 0, 100_000_000
        ),
        "pro_yearly_price_rp": _parse_int(
            cfg_map.get("pro_yearly_price_rp"), 300000, 0, 1_000_000_000
        ),
        "pro_max_devices": _parse_int(cfg_map.get("pro_max_devices"), 10, -1, 10000),
        "pro_history_days": _parse_int(cfg_map.get("pro_history_days"), 90, 1, 366),
        "upgrade_instructions": (cfg_map.get("upgrade_instructions") or "").strip(),
    }


def build_public_plans_payload(cfg_map: dict[str, str]) -> dict[str, Any]:
    """Ringkasan publik paket Gratis & Pro tanpa mengekspos data internal."""
    fcfg = get_freemium_config(cfg_map)
    return {
        "freemium_enabled": fcfg["freemium_enabled"],
        "free": {
            "tier": "free",
            "name": fcfg["free_plan_name"],
            "price_monthly_rp": 0,
            "max_devices": fcfg["free_max_devices"],
            "history_days": fcfg["free_history_days"],
            "forecast_enabled": fcfg["free_forecast_enabled"],
            "export_enabled": fcfg["free_export_enabled"],
            "anomaly_advanced": False,
        },
        "pro": {
            "tier": "pro",
            "name": fcfg["pro_plan_name"],
            "price_monthly_rp": fcfg["pro_monthly_price_rp"],
            "price_yearly_rp": fcfg["pro_yearly_price_rp"],
            "max_devices": fcfg["pro_max_devices"],
            "history_days": fcfg["pro_history_days"],
            "forecast_enabled": True,
            "export_enabled": True,
            "anomaly_advanced": True,
        },
        "upgrade_instructions": fcfg["upgrade_instructions"],
    }


def get_user_device_count(session: Session, user_id: int) -> int:
    count = session.scalar(
        select(func.count(Device.id)).where(Device.owner_user_id == user_id)
    )
    return int(count or 0)


def serialize_upgrade_request(
    req: UpgradeRequest, user: Optional[User] = None
) -> dict[str, Any]:
    """Serialisasi baris permintaan upgrade & detail pembayaran manual."""
    return {
        "id": req.id,
        "order_code": getattr(req, "order_code", None),
        "user_id": req.user_id,
        "user_name": user.name if user else None,
        "user_email": user.email if user else None,
        "requested_tier": req.requested_tier,
        "billing_cycle": req.billing_cycle,
        "amount_rp": int(req.amount_rp),
        "payment_method_id": getattr(req, "payment_method_id", None),
        "payment_method_type": getattr(req, "payment_method_type", None),
        "payment_method_label": getattr(req, "payment_method_label", None),
        "payment_account_number": getattr(req, "payment_account_number", None),
        "payment_account_holder": getattr(req, "payment_account_holder", None),
        "payment_instructions": getattr(req, "payment_instructions", None),
        "has_payment_proof": bool(getattr(req, "payment_proof_path", None)),
        "status": req.status,
        "user_note": req.user_note,
        "admin_note": req.admin_note,
        "expires_at": getattr(req, "expires_at", None),
        "submitted_at": getattr(req, "submitted_at", None),
        "created_at": req.created_at,
        "resolved_at": req.resolved_at,
    }


def resolve_user_plan(
    session: Session,
    user: User,
    cfg_map: dict[str, str],
    device_count: Optional[int] = None,
) -> dict[str, Any]:
    """Menghitung tier aktif user, status kedaluwarsa, kuota fitur, dan sisa perangkat."""
    fcfg = get_freemium_config(cfg_map)
    now_utc = int(time.time())

    raw_tier = (getattr(user, "plan_tier", "free") or "free").strip().lower()
    if raw_tier not in ("free", "pro"):
        raw_tier = "free"
    expires_at = getattr(user, "plan_expires_at", None)
    is_expired = bool(raw_tier == "pro" and expires_at is not None and expires_at <= now_utc)

    if not fcfg["freemium_enabled"]:
        effective_tier = "pro"
    else:
        effective_tier = "pro" if (raw_tier == "pro" and not is_expired) else "free"

    is_pro = effective_tier == "pro"

    if not fcfg["freemium_enabled"]:
        max_devices = -1
        history_days = 366
        forecast_enabled = True
        export_enabled = True
        anomaly_advanced = True
    elif is_pro:
        max_devices = -1 if fcfg["pro_max_devices"] <= 0 else fcfg["pro_max_devices"]
        history_days = fcfg["pro_history_days"]
        forecast_enabled = True
        export_enabled = True
        anomaly_advanced = True
    else:
        max_devices = fcfg["free_max_devices"]
        history_days = fcfg["free_history_days"]
        forecast_enabled = fcfg["free_forecast_enabled"]
        export_enabled = fcfg["free_export_enabled"]
        anomaly_advanced = False

    used_devices = (
        int(device_count)
        if device_count is not None
        else get_user_device_count(session, user.id)
    )
    remaining = None if max_devices < 0 else max(0, max_devices - used_devices)

    pending = session.scalar(
        select(UpgradeRequest)
        .where(
            UpgradeRequest.user_id == user.id,
            UpgradeRequest.status.in_(ACTIVE_UPGRADE_STATUSES),
            (
                (UpgradeRequest.status != "awaiting_payment")
                | (UpgradeRequest.expires_at.is_(None))
                | (UpgradeRequest.expires_at > now_utc)
            ),
        )
        .order_by(UpgradeRequest.created_at.desc())
        .limit(1)
    )
    latest = session.scalar(
        select(UpgradeRequest)
        .where(UpgradeRequest.user_id == user.id)
        .order_by(UpgradeRequest.created_at.desc(), UpgradeRequest.id.desc())
        .limit(1)
    )

    return {
        "freemium_enabled": fcfg["freemium_enabled"],
        "tier": raw_tier,
        "effective_tier": effective_tier,
        "plan_name": fcfg["pro_plan_name"] if is_pro else fcfg["free_plan_name"],
        "is_pro": is_pro,
        "is_expired": is_expired,
        "expires_at": expires_at,
        "updated_at": getattr(user, "plan_updated_at", None),
        "limits": {
            "max_devices": max_devices,
            "history_days": history_days,
            "forecast_enabled": forecast_enabled,
            "export_enabled": export_enabled,
            "anomaly_advanced": anomaly_advanced,
        },
        "usage": {
            "device_count": used_devices,
            "remaining_devices": remaining,
        },
        "pending_upgrade": serialize_upgrade_request(pending) if pending else None,
        "latest_upgrade": serialize_upgrade_request(latest) if latest else None,
    }


def build_plan_upgrade_exception(
    feature: str, message: str, required_tier: str = "pro"
) -> HTTPException:
    """Error HTTP 403 terstruktur agar frontend bisa memicu dialog upgrade paket."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": {
                "code": status.HTTP_403_FORBIDDEN,
                "reason": "plan_upgrade_required",
                "feature": feature,
                "required_tier": required_tier,
                "message": message,
            }
        },
    )


def _get_active_user_and_plan(
    session: Session, user_id: int, cfg_map: dict[str, str]
) -> tuple[User, dict[str, Any]]:
    user = session.get(User, int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": 404, "message": "User not found"}},
        )
    return user, resolve_user_plan(session, user, cfg_map)


def enforce_device_creation_quota(
    session: Session, user_id: int, cfg_map: dict[str, str]
) -> None:
    """Pastikan jumlah panel user tidak melebihi batas paket aktif."""
    _, plan = _get_active_user_and_plan(session, user_id, cfg_map)
    if not plan["freemium_enabled"]:
        return
    max_dev = plan["limits"]["max_devices"]
    used = plan["usage"]["device_count"]
    if max_dev >= 0 and used >= max_dev:
        raise build_plan_upgrade_exception(
            feature="device_quota",
            message=(
                f"Kuota panel paket {plan['plan_name']} sudah penuh ({used}/{max_dev} panel). "
                "Upgrade ke VoltKu Pro untuk menambah panel lagi."
            ),
        )


def enforce_series_history_access(
    session: Session,
    current: dict[str, Any],
    start_time: int,
    end_time: int,
    cfg_map: dict[str, str],
) -> None:
    """Batasi rentang historis grafik sesuai paket aktif bagi akun pembeli (role='user')."""
    if current.get("role") != "user" or current.get("user_id") is None:
        return
    _, plan = _get_active_user_and_plan(session, int(current["user_id"]), cfg_map)
    if not plan["freemium_enabled"] or plan["is_pro"]:
        return
    history_days = plan["limits"]["history_days"]
    now_utc = int(time.time())
    # Izinkan sedikit kelonggaran jam (3600 dtk) agar batas 3 hari di UI aman dari selisih detik
    allowed_span = history_days * 86400 + 3600
    earliest_allowed = now_utc - allowed_span
    if (end_time - start_time) > allowed_span or start_time < earliest_allowed:
        raise build_plan_upgrade_exception(
            feature="history_days",
            message=(
                f"Paket {plan['plan_name']} mencakup riwayat {history_days} hari terakhir. "
                "Upgrade ke VoltKu Pro untuk membuka riwayat jangka panjang."
            ),
        )


def enforce_user_feature_access(
    session: Session,
    current: dict[str, Any],
    limit_key: str,
    feature_code: str,
    message: str,
    cfg_map: dict[str, str],
) -> None:
    """Validasi apakah akun pembeli berhak memakai fitur tertentu (forecast / export)."""
    if current.get("role") != "user" or current.get("user_id") is None:
        return
    _, plan = _get_active_user_and_plan(session, int(current["user_id"]), cfg_map)
    if not plan["freemium_enabled"]:
        return
    if not plan["limits"].get(limit_key, False):
        raise build_plan_upgrade_exception(feature=feature_code, message=message)


def apply_user_plan_update(
    user: User,
    *,
    plan_tier: Optional[str] = None,
    plan_expires_at: Optional[int] = None,
    clear_expiration: bool = False,
    duration_days: Optional[int] = None,
) -> None:
    """Helper terpadu untuk memperbarui tier dan masa aktif langganan user."""
    now_utc = int(time.time())
    if plan_tier is not None:
        clean_tier = plan_tier.strip().lower()
        if clean_tier not in ("free", "pro"):
            raise ValueError("plan_tier harus 'free' atau 'pro'")
        user.plan_tier = clean_tier
        if clean_tier == "free":
            user.plan_expires_at = None

    if clear_expiration:
        user.plan_expires_at = None
    elif duration_days is not None:
        if duration_days <= 0:
            user.plan_expires_at = None
        else:
            base_ts = (
                user.plan_expires_at
                if (user.plan_expires_at and user.plan_expires_at > now_utc)
                else now_utc
            )
            user.plan_expires_at = base_ts + (int(duration_days) * 86400)
    elif plan_expires_at is not None:
        user.plan_expires_at = int(plan_expires_at) if plan_expires_at > 0 else None

    user.plan_updated_at = now_utc
