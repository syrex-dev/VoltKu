from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Setting

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


class SettingsUpdateRequest(BaseModel):
    tariff_rp: Optional[str] = None
    power_limit_w: Optional[int] = None
    alert_cooldown_min: Optional[int] = None
    extra_percent: Optional[float] = None
    report_hour: Optional[int] = None


def get_all_settings(session: Session) -> dict[str, str]:
    stmt = select(Setting)
    rows = session.scalars(stmt).all()
    return {r.key: r.value for r in rows}


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
    }


@router.get("", response_model=SettingsResponse)
def get_settings_endpoint(session: Session = Depends(get_db)):
    """Mengambil seluruh pengaturan aktif sistem."""
    settings_map = get_all_settings(session)
    return format_settings_response(settings_map)


@router.patch("", response_model=SettingsResponse)
def update_settings_endpoint(req: SettingsUpdateRequest, session: Session = Depends(get_db)):
    """Pembaruan konfigurasi dengan validasi ketat batas nilai dan presisi desimal."""
    if req.tariff_rp is not None:
        clean_str = req.tariff_rp.strip().replace(",", ".")
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
        setting_sen = session.scalar(select(Setting).where(Setting.key == "tariff_sen_per_kwh"))
        if not setting_sen:
            session.add(Setting(key="tariff_sen_per_kwh", value=str(tariff_sen)))
        else:
            setting_sen.value = str(tariff_sen)

    if req.power_limit_w is not None:
        if not (100 <= req.power_limit_w <= 25000):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {"code": 422, "message": "Power limit must be between 100 and 25000 W"}
                },
            )
        setting_p = session.scalar(select(Setting).where(Setting.key == "power_limit_w"))
        if not setting_p:
            session.add(Setting(key="power_limit_w", value=str(req.power_limit_w)))
        else:
            setting_p.value = str(req.power_limit_w)

    if req.alert_cooldown_min is not None:
        if not (5 <= req.alert_cooldown_min <= 1440):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {
                        "code": 422,
                        "message": "Alert cooldown must be between 5 and 1440 minutes",
                    }
                },
            )
        setting_c = session.scalar(select(Setting).where(Setting.key == "alert_cooldown_min"))
        if not setting_c:
            session.add(Setting(key="alert_cooldown_min", value=str(req.alert_cooldown_min)))
        else:
            setting_c.value = str(req.alert_cooldown_min)

    if req.extra_percent is not None:
        if req.extra_percent < 0.0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": 422, "message": "Extra percent must be >= 0.0"}},
            )
        setting_e = session.scalar(select(Setting).where(Setting.key == "extra_percent"))
        if not setting_e:
            session.add(Setting(key="extra_percent", value=str(req.extra_percent)))
        else:
            setting_e.value = str(req.extra_percent)

    if req.report_hour is not None:
        if not (0 <= req.report_hour <= 23):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": 422, "message": "Report hour must be between 0 and 23"}},
            )
        setting_r = session.scalar(select(Setting).where(Setting.key == "report_hour"))
        if not setting_r:
            session.add(Setting(key="report_hour", value=str(req.report_hour)))
        else:
            setting_r.value = str(req.report_hour)

    session.commit()
    settings_map = get_all_settings(session)
    return format_settings_response(settings_map)
