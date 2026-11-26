import json
import re
import time
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Device, DiscountCode, SubscriptionPlan, UpgradeRequest, User

ACTIVE_UPGRADE_STATUSES = ("pending", "awaiting_payment", "verifying")
PLAN_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")
DISCOUNT_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,31}$")
ALLOWED_DISCOUNT_TYPES = ("percent", "fixed_rp")


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


def _round_percent_rp(amount_rp: int, pct: int) -> int:
    if amount_rp <= 0 or pct <= 0:
        return 0
    raw = (Decimal(amount_rp) * Decimal(pct)) / Decimal(100)
    rounded = int(raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return max(0, min(amount_rp, rounded))


def parse_plan_features(plan: SubscriptionPlan) -> list[str]:
    """Mengurai daftar poin keunggulan dari features_json atau menyusun otomatis dari kuota."""
    if plan.features_json:
        try:
            parsed = json.loads(plan.features_json)
            if isinstance(parsed, list):
                cleaned = [str(x).strip() for x in parsed if str(x).strip()]
                if cleaned:
                    return cleaned
        except (ValueError, TypeError):
            pass

    max_dev_label = (
        "Panel aktif tanpa batas"
        if plan.max_devices < 0
        else f"Maks. {plan.max_devices} panel aktif"
    )
    items = [
        max_dev_label,
        "Pantau Live real-time 10 detik",
        f"Grafik historis hingga {plan.history_days} hari",
    ]
    if plan.forecast_enabled:
        items.append("Proyeksi tagihan akhir bulan otomatis")
    if plan.export_enabled:
        items.append("Ekspor laporan konsumsi CSV")
    if plan.anomaly_advanced:
        items.append("Deteksi anomali lengkap L2/L3")
    return items


def is_plan_promo_active(plan: SubscriptionPlan, now_utc: Optional[int] = None) -> bool:
    """Mengecek apakah promo harga coret pada paket sedang aktif berdasarkan jadwal UTC."""
    ptype = (plan.promo_discount_type or "").strip().lower()
    pval = int(plan.promo_discount_value or 0)
    if ptype not in ALLOWED_DISCOUNT_TYPES or pval <= 0:
        return False
    ts = now_utc if now_utc is not None else int(time.time())
    if plan.promo_starts_at is not None and ts < int(plan.promo_starts_at):
        return False
    if plan.promo_expires_at is not None and ts >= int(plan.promo_expires_at):
        return False
    return True


def compute_plan_cycle_pricing(
    plan: SubscriptionPlan,
    cycle: str,
    now_utc: Optional[int] = None,
) -> tuple[int, int, int, bool]:
    """Menghitung (harga_dasar, diskon_promo, harga_efektif, promo_aktif) dengan Decimal/int."""
    base_price = (
        int(plan.price_yearly_rp or 0)
        if cycle == "yearly"
        else int(plan.price_monthly_rp or 0)
    )
    base_price = max(0, base_price)
    if base_price <= 0 or not is_plan_promo_active(plan, now_utc=now_utc):
        return base_price, 0, base_price, False

    ptype = (plan.promo_discount_type or "").strip().lower()
    pval = int(plan.promo_discount_value or 0)
    if ptype == "percent":
        promo_disc = _round_percent_rp(base_price, min(100, pval))
    else:
        promo_disc = min(base_price, max(0, pval))
    effective = max(0, base_price - promo_disc)
    return base_price, promo_disc, effective, promo_disc > 0


def serialize_plan(
    plan: SubscriptionPlan,
    *,
    now_utc: Optional[int] = None,
) -> dict[str, Any]:
    """Serialisasi baris SubscriptionPlan beserta kalkulasi harga promo & hemat tahunan."""
    ts = now_utc if now_utc is not None else int(time.time())
    base_mo, disc_mo, eff_mo, promo_mo_active = compute_plan_cycle_pricing(
        plan, "monthly", now_utc=ts
    )
    base_yr, disc_yr, eff_yr, promo_yr_active = compute_plan_cycle_pricing(
        plan, "yearly", now_utc=ts
    )
    promo_active = promo_mo_active or promo_yr_active

    yearly_full_from_eff = eff_mo * 12
    yearly_savings_rp = max(0, yearly_full_from_eff - eff_yr) if eff_mo > 0 and eff_yr > 0 else 0
    yearly_savings_pct = (
        int(
            (Decimal(yearly_savings_rp) * Decimal(100) / Decimal(yearly_full_from_eff)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        if yearly_full_from_eff > 0 and yearly_savings_rp > 0
        else 0
    )

    return {
        "id": plan.id,
        "slug": plan.slug,
        "tier": plan.slug,
        "name": plan.name,
        "description": plan.description or "",
        "badge_text": plan.badge_text or "",
        "price_monthly_rp": base_mo,
        "price_yearly_rp": base_yr,
        "effective_monthly_price_rp": eff_mo,
        "effective_yearly_price_rp": eff_yr,
        "monthly_promo_discount_rp": disc_mo,
        "yearly_promo_discount_rp": disc_yr,
        "promo_active": promo_active,
        "promo_discount_type": plan.promo_discount_type,
        "promo_discount_value": int(plan.promo_discount_value or 0),
        "promo_label": plan.promo_label or "",
        "promo_starts_at": plan.promo_starts_at,
        "promo_expires_at": plan.promo_expires_at,
        "yearly_savings_rp": yearly_savings_rp,
        "yearly_savings_pct": yearly_savings_pct,
        "max_devices": int(plan.max_devices),
        "history_days": int(plan.history_days),
        "forecast_enabled": bool(plan.forecast_enabled),
        "export_enabled": bool(plan.export_enabled),
        "anomaly_advanced": bool(plan.anomaly_advanced),
        "features": parse_plan_features(plan),
        "is_default_free": bool(plan.is_default_free),
        "is_recommended": bool(plan.is_recommended),
        "is_active": bool(plan.is_active),
        "sort_order": int(plan.sort_order),
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
    }


def serialize_discount_code(dc: DiscountCode, now_utc: Optional[int] = None) -> dict[str, Any]:
    ts = now_utc if now_utc is not None else int(time.time())
    expired = bool(dc.expires_at is not None and ts >= int(dc.expires_at))
    not_started = bool(dc.starts_at is not None and ts < int(dc.starts_at))
    exhausted = bool(dc.max_uses is not None and int(dc.used_count or 0) >= int(dc.max_uses))
    currently_valid = bool(dc.is_active) and not expired and not not_started and not exhausted
    return {
        "id": dc.id,
        "code": dc.code,
        "label": dc.label or "",
        "discount_type": dc.discount_type,
        "discount_value": int(dc.discount_value),
        "max_discount_rp": dc.max_discount_rp,
        "min_purchase_rp": int(dc.min_purchase_rp or 0),
        "target_plan_slug": dc.target_plan_slug,
        "target_cycle": dc.target_cycle,
        "max_uses": dc.max_uses,
        "used_count": int(dc.used_count or 0),
        "starts_at": dc.starts_at,
        "expires_at": dc.expires_at,
        "is_active": bool(dc.is_active),
        "currently_valid": currently_valid,
        "is_expired": expired,
        "is_exhausted": exhausted,
        "created_at": dc.created_at,
        "updated_at": dc.updated_at,
    }


def get_freemium_config(cfg_map: dict[str, str]) -> dict[str, Any]:
    """Mengurai konfigurasi dasar Freemium dari app_config (fallback dan global toggle)."""
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


def ensure_default_plans_seeded(
    session: Session,
    cfg_map: Optional[dict[str, str]] = None,
) -> list[SubscriptionPlan]:
    """Memastikan minimal paket Gratis & Pro tersedia di tabel subscription_plans."""
    existing = session.scalars(
        select(SubscriptionPlan).order_by(
            SubscriptionPlan.sort_order.asc(), SubscriptionPlan.id.asc()
        )
    ).all()
    if existing:
        return list(existing)

    fcfg = get_freemium_config(cfg_map or {})
    now_ts = int(time.time())
    free_plan = SubscriptionPlan(
        slug="free",
        name=fcfg["free_plan_name"],
        description="Cocok untuk coba pantau panel rumah",
        badge_text=None,
        price_monthly_rp=0,
        price_yearly_rp=0,
        max_devices=fcfg["free_max_devices"],
        history_days=fcfg["free_history_days"],
        forecast_enabled=1 if fcfg["free_forecast_enabled"] else 0,
        export_enabled=1 if fcfg["free_export_enabled"] else 0,
        anomaly_advanced=0,
        features_json=json.dumps(
            [
                f"Maks. {fcfg['free_max_devices']} panel aktif",
                "Pantau Live real-time 10 detik",
                f"Grafik hingga {fcfg['free_history_days']} hari",
            ]
        ),
        is_default_free=1,
        is_recommended=0,
        is_active=1,
        sort_order=1,
        created_at=now_ts,
        updated_at=now_ts,
    )
    pro_dev_text = (
        "Panel aktif tanpa batas"
        if fcfg["pro_max_devices"] < 0
        else f"Hingga {fcfg['pro_max_devices']} panel aktif"
    )
    pro_plan = SubscriptionPlan(
        slug="pro",
        name=fcfg["pro_plan_name"],
        description="Kendali analisa energi lengkap untuk rumah & usaha",
        badge_text="Rekomendasi",
        price_monthly_rp=fcfg["pro_monthly_price_rp"],
        price_yearly_rp=fcfg["pro_yearly_price_rp"],
        max_devices=fcfg["pro_max_devices"],
        history_days=fcfg["pro_history_days"],
        forecast_enabled=1,
        export_enabled=1,
        anomaly_advanced=1,
        features_json=json.dumps(
            [
                pro_dev_text,
                f"Grafik historis hingga {fcfg['pro_history_days']} hari",
                "Proyeksi tagihan akhir bulan otomatis",
                "Ekspor laporan konsumsi CSV",
                "Deteksi anomali lengkap L2/L3",
            ]
        ),
        is_default_free=0,
        is_recommended=1,
        is_active=1,
        sort_order=2,
        created_at=now_ts,
        updated_at=now_ts,
    )
    session.add(free_plan)
    session.add(pro_plan)
    session.flush()
    return [free_plan, pro_plan]


def sync_legacy_app_config_to_default_plans(
    session: Session,
    cfg_map: dict[str, str],
) -> None:
    """Sinkronkan kunci lama free_*/pro_* di /api/admin/app-settings ke tabel paket."""
    plans = ensure_default_plans_seeded(session, cfg_map)
    fcfg = get_freemium_config(cfg_map)
    now_ts = int(time.time())
    by_slug = {p.slug: p for p in plans}

    free_row = by_slug.get("free") or next((p for p in plans if p.is_default_free), None)
    if free_row:
        free_row.name = fcfg["free_plan_name"]
        free_row.max_devices = fcfg["free_max_devices"]
        free_row.history_days = fcfg["free_history_days"]
        free_row.forecast_enabled = 1 if fcfg["free_forecast_enabled"] else 0
        free_row.export_enabled = 1 if fcfg["free_export_enabled"] else 0
        free_row.updated_at = now_ts

    pro_row = by_slug.get("pro")
    if pro_row:
        pro_row.name = fcfg["pro_plan_name"]
        pro_row.price_monthly_rp = fcfg["pro_monthly_price_rp"]
        pro_row.price_yearly_rp = fcfg["pro_yearly_price_rp"]
        pro_row.max_devices = fcfg["pro_max_devices"]
        pro_row.history_days = fcfg["pro_history_days"]
        pro_row.updated_at = now_ts
    session.flush()


def build_public_plans_payload(
    cfg_map: dict[str, str],
    session: Optional[Session] = None,
) -> dict[str, Any]:
    """Ringkasan publik seluruh paket aktif beserta fallback free/pro untuk kompatibilitas."""
    fcfg = get_freemium_config(cfg_map)
    if session is None:
        return {
            "freemium_enabled": fcfg["freemium_enabled"],
            "free": {
                "tier": "free",
                "slug": "free",
                "name": fcfg["free_plan_name"],
                "price_monthly_rp": 0,
                "effective_monthly_price_rp": 0,
                "max_devices": fcfg["free_max_devices"],
                "history_days": fcfg["free_history_days"],
                "forecast_enabled": fcfg["free_forecast_enabled"],
                "export_enabled": fcfg["free_export_enabled"],
                "anomaly_advanced": False,
                "is_default_free": True,
                "promo_active": False,
            },
            "pro": {
                "tier": "pro",
                "slug": "pro",
                "name": fcfg["pro_plan_name"],
                "price_monthly_rp": fcfg["pro_monthly_price_rp"],
                "price_yearly_rp": fcfg["pro_yearly_price_rp"],
                "effective_monthly_price_rp": fcfg["pro_monthly_price_rp"],
                "effective_yearly_price_rp": fcfg["pro_yearly_price_rp"],
                "max_devices": fcfg["pro_max_devices"],
                "history_days": fcfg["pro_history_days"],
                "forecast_enabled": True,
                "export_enabled": True,
                "anomaly_advanced": True,
                "is_default_free": False,
                "promo_active": False,
            },
            "items": [],
            "upgrade_instructions": fcfg["upgrade_instructions"],
        }

    all_rows = ensure_default_plans_seeded(session, cfg_map)
    active_rows = [p for p in all_rows if p.is_active]
    now_ts = int(time.time())
    items = [serialize_plan(p, now_utc=now_ts) for p in active_rows]

    free_item = next(
        (x for x in items if x["is_default_free"] or x["slug"] == "free"),
        None,
    )
    if free_item is None:
        raw_free = next((p for p in all_rows if p.is_default_free or p.slug == "free"), None)
        free_item = serialize_plan(raw_free, now_utc=now_ts) if raw_free else {
            "tier": "free",
            "slug": "free",
            "name": fcfg["free_plan_name"],
            "price_monthly_rp": 0,
            "effective_monthly_price_rp": 0,
            "max_devices": fcfg["free_max_devices"],
            "history_days": fcfg["free_history_days"],
            "forecast_enabled": fcfg["free_forecast_enabled"],
            "export_enabled": fcfg["free_export_enabled"],
            "anomaly_advanced": False,
            "is_default_free": True,
            "promo_active": False,
        }

    paid_items = [x for x in items if not x["is_default_free"] and x["slug"] != "free"]
    pro_item = next((x for x in paid_items if x["slug"] == "pro"), None)
    if pro_item is None:
        pro_item = paid_items[0] if paid_items else {
            "tier": "pro",
            "slug": "pro",
            "name": fcfg["pro_plan_name"],
            "price_monthly_rp": fcfg["pro_monthly_price_rp"],
            "price_yearly_rp": fcfg["pro_yearly_price_rp"],
            "effective_monthly_price_rp": fcfg["pro_monthly_price_rp"],
            "effective_yearly_price_rp": fcfg["pro_yearly_price_rp"],
            "max_devices": fcfg["pro_max_devices"],
            "history_days": fcfg["pro_history_days"],
            "forecast_enabled": True,
            "export_enabled": True,
            "anomaly_advanced": True,
            "is_default_free": False,
            "promo_active": False,
        }

    return {
        "freemium_enabled": fcfg["freemium_enabled"],
        "free": free_item,
        "pro": pro_item,
        "items": items,
        "upgrade_instructions": fcfg["upgrade_instructions"],
    }


def evaluate_checkout_pricing(
    session: Session,
    *,
    plan: SubscriptionPlan,
    billing_cycle: str,
    discount_code_raw: Optional[str] = None,
    now_utc: Optional[int] = None,
) -> dict[str, Any]:
    """Menghitung total pembayaran deterministik + memvalidasi kode promo jika diisi."""
    ts = now_utc if now_utc is not None else int(time.time())
    if plan.is_default_free or plan.slug == "free":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {"code": 422, "message": "Pilih paket berbayar untuk melanjutkan upgrade."}
            },
        )

    base_amount_rp, promo_discount_rp, subtotal_rp, promo_active = compute_plan_cycle_pricing(
        plan, billing_cycle, now_utc=ts
    )

    clean_code = (discount_code_raw or "").strip().upper()
    dc: Optional[DiscountCode] = None
    voucher_discount_rp = 0

    if clean_code:
        dc = session.scalar(select(DiscountCode).where(DiscountCode.code == clean_code))
        if not dc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": {
                        "code": 404,
                        "message": f"Kode promo '{clean_code}' tidak ditemukan.",
                    }
                },
            )
        if not dc.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": 422, "message": "Kode promo sedang tidak aktif."}},
            )
        if dc.starts_at is not None and ts < int(dc.starts_at):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": 422, "message": "Periode kode promo belum dimulai."}},
            )
        if dc.expires_at is not None and ts >= int(dc.expires_at):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": 422, "message": "Kode promo sudah kedaluwarsa."}},
            )
        if dc.max_uses is not None and int(dc.used_count or 0) >= int(dc.max_uses):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": {"code": 409, "message": "Kuota pemakaian kode promo sudah habis."}
                },
            )
        if dc.target_plan_slug and dc.target_plan_slug.strip().lower() != plan.slug:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {
                        "code": 422,
                        "message": f"Kode promo ini khusus untuk paket '{dc.target_plan_slug}'.",
                    }
                },
            )
        if dc.target_cycle and dc.target_cycle.strip().lower() != billing_cycle:
            cycle_lbl = "Tahunan" if dc.target_cycle.strip().lower() == "yearly" else "Bulanan"
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {
                        "code": 422,
                        "message": f"Kode promo ini khusus untuk durasi {cycle_lbl}.",
                    }
                },
            )
        min_rp = int(dc.min_purchase_rp or 0)
        if subtotal_rp < min_rp:
            formatted_min = f"{min_rp:,}".replace(",", ".")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {
                        "code": 422,
                        "message": f"Minimal total paket Rp {formatted_min} untuk kode ini.",
                    }
                },
            )

        if dc.discount_type == "percent":
            voucher_discount_rp = _round_percent_rp(subtotal_rp, min(100, int(dc.discount_value)))
            if dc.max_discount_rp is not None and int(dc.max_discount_rp) > 0:
                voucher_discount_rp = min(voucher_discount_rp, int(dc.max_discount_rp))
        else:
            voucher_discount_rp = min(subtotal_rp, max(0, int(dc.discount_value)))

    final_amount_rp = max(0, subtotal_rp - voucher_discount_rp)
    return {
        "plan": plan,
        "plan_slug": plan.slug,
        "plan_name": plan.name,
        "billing_cycle": billing_cycle,
        "base_amount_rp": base_amount_rp,
        "promo_discount_rp": promo_discount_rp,
        "promo_active": promo_active,
        "promo_label": plan.promo_label or "",
        "subtotal_after_promo_rp": subtotal_rp,
        "discount_code_obj": dc,
        "discount_code": dc.code if dc else None,
        "discount_label": dc.label if dc else None,
        "voucher_discount_rp": voucher_discount_rp,
        "final_amount_rp": final_amount_rp,
    }


def release_discount_usage(session: Session, entry: UpgradeRequest) -> None:
    """Mengembalikan 1 kuota pemakaian kode promo saat tagihan dibatalkan atau kedaluwarsa."""
    dc_id = getattr(entry, "discount_code_id", None)
    if not dc_id:
        return
    dc = session.get(DiscountCode, int(dc_id))
    if dc and int(dc.used_count or 0) > 0:
        dc.used_count = int(dc.used_count) - 1
        session.flush()


def get_user_device_count(session: Session, user_id: int) -> int:
    count = session.scalar(
        select(func.count(Device.id)).where(Device.owner_user_id == user_id)
    )
    return int(count or 0)


def serialize_upgrade_request(
    req: UpgradeRequest, user: Optional[User] = None
) -> dict[str, Any]:
    """Serialisasi baris permintaan upgrade & rincian diskon/pembayaran manual."""
    base_rp = int(getattr(req, "base_amount_rp", 0) or 0)
    amount_rp = int(req.amount_rp or 0)
    if base_rp <= 0 and amount_rp > 0:
        base_rp = amount_rp
    return {
        "id": req.id,
        "order_code": getattr(req, "order_code", None),
        "user_id": req.user_id,
        "user_name": user.name if user else None,
        "user_email": user.email if user else None,
        "requested_tier": req.requested_tier,
        "plan_id": getattr(req, "plan_id", None),
        "plan_name_snapshot": getattr(req, "plan_name_snapshot", None)
        or (req.requested_tier.upper() if req.requested_tier else "PRO"),
        "billing_cycle": req.billing_cycle,
        "base_amount_rp": base_rp,
        "promo_discount_rp": int(getattr(req, "promo_discount_rp", 0) or 0),
        "discount_code": getattr(req, "discount_code", None),
        "voucher_discount_rp": int(getattr(req, "voucher_discount_rp", 0) or 0),
        "amount_rp": amount_rp,
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
    """Menghitung paket aktif user (lintas paket dinamis), masa berlaku, kuota, dan sisa panel."""
    fcfg = get_freemium_config(cfg_map)
    all_plans = ensure_default_plans_seeded(session, cfg_map)
    by_id = {p.id: p for p in all_plans}
    by_slug = {p.slug: p for p in all_plans}
    free_row = by_slug.get("free") or next(
        (p for p in all_plans if p.is_default_free), all_plans[0]
    )

    now_utc = int(time.time())
    raw_tier = (getattr(user, "plan_tier", "free") or "free").strip().lower()
    user_plan_id = getattr(user, "plan_id", None)
    assigned_row = (by_id.get(user_plan_id) if user_plan_id else None) or by_slug.get(raw_tier)
    if assigned_row is None:
        assigned_row = free_row
        raw_tier = free_row.slug

    is_paid_assigned = (not bool(assigned_row.is_default_free)) and assigned_row.slug != "free"
    expires_at = getattr(user, "plan_expires_at", None)
    is_expired = bool(is_paid_assigned and expires_at is not None and expires_at <= now_utc)

    if not fcfg["freemium_enabled"]:
        effective_row = by_slug.get("pro") or assigned_row
        effective_tier = "pro"
        is_pro = True
        max_devices = -1
        history_days = 366
        forecast_enabled = True
        export_enabled = True
        anomaly_advanced = True
        plan_display_name = (
            assigned_row.name if (is_paid_assigned and not is_expired) else effective_row.name
        )
    else:
        active_row = free_row if (is_expired or not is_paid_assigned) else assigned_row
        effective_tier = active_row.slug
        is_pro = (not bool(active_row.is_default_free)) and active_row.slug != "free"
        max_devices = -1 if int(active_row.max_devices) <= 0 else int(active_row.max_devices)
        history_days = int(active_row.history_days)
        forecast_enabled = bool(active_row.forecast_enabled)
        export_enabled = bool(active_row.export_enabled)
        anomaly_advanced = bool(active_row.anomaly_advanced)
        plan_display_name = active_row.name

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
        "plan_id": assigned_row.id if assigned_row else None,
        "plan_name": plan_display_name,
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
                "Upgrade paket untuk menambah panel lagi."
            ),
        )


def enforce_series_history_access(
    session: Session,
    current: dict[str, Any],
    start_time: int,
    end_time: int,
    cfg_map: dict[str, str],
) -> None:
    """Batasi rentang historis grafik sesuai batas hari paket aktif akun pembeli."""
    if current.get("role") != "user" or current.get("user_id") is None:
        return
    _, plan = _get_active_user_and_plan(session, int(current["user_id"]), cfg_map)
    if not plan["freemium_enabled"]:
        return
    history_days = plan["limits"]["history_days"]
    now_utc = int(time.time())
    # Izinkan sedikit kelonggaran jam (3600 dtk) agar batas hari di UI aman dari selisih detik
    allowed_span = history_days * 86400 + 3600
    earliest_allowed = now_utc - allowed_span
    if (end_time - start_time) > allowed_span or start_time < earliest_allowed:
        raise build_plan_upgrade_exception(
            feature="history_days",
            message=(
                f"Paket {plan['plan_name']} mencakup riwayat {history_days} hari terakhir. "
                "Upgrade paket untuk membuka riwayat lebih panjang."
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
    session: Optional[Session] = None,
) -> None:
    """Helper terpadu untuk memperbarui paket (dinamis) dan masa aktif langganan user."""
    now_utc = int(time.time())
    if plan_tier is not None:
        clean_tier = plan_tier.strip().lower()
        if not PLAN_SLUG_RE.match(clean_tier):
            raise ValueError("Slug paket tidak valid (gunakan 2-32 huruf kecil/angka/strip)")

        if session is not None:
            all_plans = ensure_default_plans_seeded(session)
            matched = next((p for p in all_plans if p.slug == clean_tier), None)
            if not matched:
                raise ValueError(f"Paket '{clean_tier}' tidak ditemukan")
            user.plan_tier = matched.slug
            user.plan_id = matched.id
            if matched.is_default_free or matched.slug == "free":
                user.plan_expires_at = None
        else:
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
