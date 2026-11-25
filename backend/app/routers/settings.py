from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Setting, UserSetting
from app.services.scheduler import reschedule_daily_report

router = APIRouter(
    prefix="/api/settings", tags=["Settings"], dependencies=[Depends(get_current_user)]
)


class SettingsResponse(BaseModel):
    tariff_rp: str
    tariff_sen: int
    power_limit_w: int
    alert_cooldown_min: int
    extra_percent: float
    report_hour: int
    report_enabled: bool


class SettingsUpdateRequest(BaseModel):
    tariff_rp: Optional[str] = None
    power_limit_w: Optional[int] = None
    alert_cooldown_min: Optional[int] = None
    extra_percent: Optional[float] = None
    report_hour: Optional[int] = None
    report_enabled: Optional[bool] = None


def get_all_settings(session: Session, user_id: Optional[int] = None) -> dict[str, str]:
    rows = session.scalars(select(Setting)).all()
    merged = {r.key: r.value for r in rows}
    if user_id is not None:
        user_rows = session.scalars(
            select(UserSetting).where(UserSetting.user_id == user_id)
        ).all()
        for ur in user_rows:
            merged[ur.key] = ur.value
    return merged


def format_settings_response(settings_map: dict[str, str]) -> dict[str, Any]:
    tariff_sen = int(settings_map.get("tariff_sen_per_kwh", "144470"))
    tariff_rp = f"{Decimal(tariff_sen) / Decimal(100):.2f}"
    return {
        "tariff_rp": tariff_rp,
        "tariff_sen": tariff_sen,
        "power_limit_w": int(settings_map.get("power_limit_w", "2200")),
        "alert_cooldown_min": int(settings_map.get("alert_cooldown_min", "30")),
        "extra_percent": float(settings_map.get("extra_percent", "0.0")),
        "report_hour": int(settings_map.get("report_hour", "21")),
        "report_enabled": settings_map.get("report_enabled", "true").lower() in ("true", "1"),
    }


def _upsert_setting(
    session: Session, key: str, value: str, user_id: Optional[int] = None
) -> None:
    if user_id is not None:
        existing_user = session.scalar(
            select(UserSetting).where(UserSetting.user_id == user_id, UserSetting.key == key)
        )
        if not existing_user:
            session.add(UserSetting(user_id=user_id, key=key, value=value))
        else:
            existing_user.value = value
        return

    existing_global = session.scalar(select(Setting).where(Setting.key == key))
    if not existing_global:
        session.add(Setting(key=key, value=value))
    else:
        existing_global.value = value


@router.get("", response_model=SettingsResponse)
def get_settings_endpoint(
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Mengambil pengaturan aktif (per tenant bila role=user, global bila admin)."""
    uid = current.get("user_id") if current.get("role") == "user" else None
    settings_map = get_all_settings(session, user_id=uid)
    return format_settings_response(settings_map)


def apply_settings_updates(
    session: Session,
    *,
    tariff_rp: Optional[str] = None,
    power_limit_w: Optional[int] = None,
    alert_cooldown_min: Optional[int] = None,
    extra_percent: Optional[float] = None,
    report_hour: Optional[int] = None,
    report_enabled: Optional[bool] = None,
    user_id: Optional[int] = None,
) -> None:
    """Validasi dan simpan pembaruan pengaturan operasional (global atau per tenant)."""
    if tariff_rp is not None:
        clean_str = tariff_rp.strip().replace(",", ".")
        try:
            dec = Decimal(clean_str)
        except InvalidOperation as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": 422, "message": "Tariff must be a valid numeric string"}},
            ) from err

        if dec.is_nan() or dec.is_infinite():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": 422, "message": "Tariff cannot be NaN or Infinite"}},
            )

        if "." in clean_str:
            dec_part = clean_str.split(".")[1]
            if len(dec_part) > 2:
                err_msg = "Tariff must have at most 2 decimal places (do not round silently)"
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={"error": {"code": 422, "message": err_msg}},
                )

        if dec <= Decimal("0") or dec > Decimal("100000"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {"code": 422, "message": "Tariff must be between 0 and 100,000 Rp/kWh"}
                },
            )

        tariff_sen = int((dec * Decimal(100)).quantize(Decimal("1")))
        _upsert_setting(session, "tariff_sen_per_kwh", str(tariff_sen), user_id=user_id)

    if power_limit_w is not None:
        if not (100 <= power_limit_w <= 25000):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {"code": 422, "message": "Power limit must be between 100 and 25000 W"}
                },
            )
        _upsert_setting(session, "power_limit_w", str(power_limit_w), user_id=user_id)

    if alert_cooldown_min is not None:
        if not (5 <= alert_cooldown_min <= 1440):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {
                        "code": 422,
                        "message": "Alert cooldown must be between 5 and 1440 minutes",
                    }
                },
            )
        _upsert_setting(session, "alert_cooldown_min", str(alert_cooldown_min), user_id=user_id)

    if extra_percent is not None:
        if extra_percent < 0.0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": 422, "message": "Extra percent must be >= 0.0"}},
            )
        _upsert_setting(session, "extra_percent", str(extra_percent), user_id=user_id)

    if report_hour is not None:
        if not (0 <= report_hour <= 23):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": 422, "message": "Report hour must be between 0 and 23"}},
            )
        _upsert_setting(session, "report_hour", str(report_hour), user_id=user_id)
        if user_id is None:
            reschedule_daily_report(report_hour)

    if report_enabled is not None:
        val_str = "true" if report_enabled else "false"
        _upsert_setting(session, "report_enabled", val_str, user_id=user_id)


@router.patch("", response_model=SettingsResponse)
def update_settings_endpoint(
    req: SettingsUpdateRequest,
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Pembaruan konfigurasi (per tenant bila user, global bila admin)."""
    uid = current.get("user_id") if current.get("role") == "user" else None
    apply_settings_updates(
        session=session,
        tariff_rp=req.tariff_rp,
        power_limit_w=req.power_limit_w,
        alert_cooldown_min=req.alert_cooldown_min,
        extra_percent=req.extra_percent,
        report_hour=req.report_hour,
        report_enabled=req.report_enabled,
        user_id=uid,
    )
    session.commit()
    settings_map = get_all_settings(session, user_id=uid)
    return format_settings_response(settings_map)
