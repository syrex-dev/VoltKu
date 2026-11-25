import calendar
from datetime import datetime, time, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DailyStat, Device, HourlyStat, Reading, Setting, UserSetting
from app.services.cost import calculate_cost_rp

TZ_WIB = ZoneInfo("Asia/Jakarta")


def _get_effective_setting_value(
    session: Session, key: str, user_id: Optional[int] = None
) -> Optional[str]:
    if user_id is not None:
        u_row = session.scalar(
            select(UserSetting).where(UserSetting.user_id == user_id, UserSetting.key == key)
        )
        if u_row and u_row.value:
            return u_row.value
    g_row = session.scalar(select(Setting).where(Setting.key == key))
    return g_row.value if g_row else None


def get_current_tariff_sen(session: Session, user_id: Optional[int] = None) -> int:
    """Mengambil tarif aktif saat ini dalam satuan sen (integer)."""
    val = _get_effective_setting_value(session, "tariff_sen_per_kwh", user_id=user_id)
    if val:
        try:
            return int(val)
        except ValueError:
            pass
    return 144470


def get_extra_percent(session: Session, user_id: Optional[int] = None) -> float:
    """Mengambil persentase biaya tambahan/pajak aktif."""
    val = _get_effective_setting_value(session, "extra_percent", user_id=user_id)
    if val:
        try:
            return float(val)
        except ValueError:
            pass
    return 0.0


def calculate_device_summary(
    session: Session,
    device_id: str,
    range: Optional[str] = None,
    from_ts: Optional[int] = None,
    to_ts: Optional[int] = None,
    now_dt: Optional[datetime] = None,
) -> dict[str, Any]:
    """Menghitung rangkuman konsumsi kWh, biaya, rata-rata, dan beban puncak periode tertentu."""
    device = session.scalar(select(Device).where(Device.id == device_id))
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": 404, "message": f"Device '{device_id}' not found"}},
        )

    now_wib = now_dt.astimezone(TZ_WIB) if now_dt else datetime.now(tz=TZ_WIB)
    active_tariff_sen = get_current_tariff_sen(session, user_id=device.owner_user_id)
    extra_percent = get_extra_percent(session, user_id=device.owner_user_id)

    if range:
        if from_ts is not None or to_ts is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {
                        "code": 422,
                        "message": "Cannot specify both 'range' and 'from'/'to' parameters",
                    }
                },
            )
        if range == "today":
            start_wib = datetime.combine(now_wib.date(), time(0, 0, 0), tzinfo=TZ_WIB)
            start_time = int(start_wib.timestamp())
            end_time = int(now_wib.timestamp())
        elif range == "week":
            # Minggu dimulai hari Senin
            start_date = now_wib.date() - timedelta(days=now_wib.weekday())
            start_wib = datetime.combine(start_date, time(0, 0, 0), tzinfo=TZ_WIB)
            start_time = int(start_wib.timestamp())
            end_time = int(now_wib.timestamp())
        elif range == "month":
            start_date = now_wib.date().replace(day=1)
            start_wib = datetime.combine(start_date, time(0, 0, 0), tzinfo=TZ_WIB)
            start_time = int(start_wib.timestamp())
            end_time = int(now_wib.timestamp())
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": {
                        "code": 422,
                        "message": "Invalid range parameter. Use today, week, or month.",
                    }
                },
            )
    else:
        now_utc = int(now_wib.astimezone(timezone.utc).timestamp())
        end_time = to_ts if to_ts is not None else now_utc
        start_time = from_ts if from_ts is not None else (end_time - 86400)

    delta_sec = end_time - start_time
    if delta_sec < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {"code": 422, "message": "'from' timestamp must be <= 'to' timestamp"}
            },
        )
    if delta_sec > 366 * 86400:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": 422, "message": "Time range cannot exceed 366 days"}},
        )

    # Cek apakah rentang tepat mencakup hari-hari penuh yang lampau (tanpa jam parsial)
    dt_from = datetime.fromtimestamp(start_time, tz=TZ_WIB)
    dt_to = datetime.fromtimestamp(end_time, tz=TZ_WIB)

    is_exact_midnight_start = dt_from.time() == time(0, 0, 0)
    is_exact_midnight_end = dt_to.time() in (time(23, 59, 59), time(0, 0, 0))
    is_all_past_days = dt_to.date() < now_wib.date()

    cost_estimated = True
    total_cost_rp = 0

    if range == "today":
        cost_estimated = True
        stmt_today = select(func.sum(Reading.delta_kwh)).where(
            Reading.device_id == device_id,
            Reading.ts >= start_time,
            Reading.ts <= end_time,
        )
        today_kwh = float(session.scalar(stmt_today) or 0.0)
        total_cost_rp = calculate_cost_rp(today_kwh, active_tariff_sen, extra_percent)
    elif range in ("week", "month"):
        cost_estimated = True
        start_day_str = dt_from.strftime("%Y-%m-%d")
        yesterday_wib = now_wib.date() - timedelta(days=1)
        yesterday_str = yesterday_wib.strftime("%Y-%m-%d")
        past_cost = 0
        if start_day_str <= yesterday_str:
            stmt_past = select(func.sum(DailyStat.cost_rp)).where(
                DailyStat.device_id == device_id,
                DailyStat.day >= start_day_str,
                DailyStat.day <= yesterday_str,
            )
            past_cost = int(session.scalar(stmt_past) or 0)

        # Tambahkan hari berjalan (today)
        start_today_ts = int(
            datetime.combine(now_wib.date(), time(0, 0, 0), tzinfo=TZ_WIB).timestamp()
        )
        stmt_today = select(func.sum(Reading.delta_kwh)).where(
            Reading.device_id == device_id,
            Reading.ts >= start_today_ts,
            Reading.ts <= end_time,
        )
        today_kwh = float(session.scalar(stmt_today) or 0.0)
        today_cost = calculate_cost_rp(today_kwh, active_tariff_sen, extra_percent)
        total_cost_rp = past_cost + today_cost
    elif is_exact_midnight_start and is_exact_midnight_end and is_all_past_days:
        # Rentang pas batas hari lampau -> ambil akumulasi cost_rp harian (tarif beku)
        cost_estimated = False
        start_day_str = dt_from.strftime("%Y-%m-%d")
        end_day_str = (
            (dt_to - timedelta(seconds=1)).strftime("%Y-%m-%d")
            if dt_to.time() == time(0, 0, 0)
            else dt_to.strftime("%Y-%m-%d")
        )

        stmt_cost = select(func.sum(DailyStat.cost_rp)).where(
            DailyStat.device_id == device_id,
            DailyStat.day >= start_day_str,
            DailyStat.day <= end_day_str,
        )
        total_cost_rp = int(session.scalar(stmt_cost) or 0)
    else:
        # Rentang sub-hari atau rentang kustom campuran
        cost_estimated = True
        cur_date = dt_from.date()
        accum_cost = 0
        while cur_date <= dt_to.date():
            d_start_dt = datetime.combine(cur_date, time(0, 0, 0), tzinfo=TZ_WIB)
            d_end_dt = datetime.combine(cur_date, time(23, 59, 59), tzinfo=TZ_WIB)
            d_start = max(start_time, int(d_start_dt.timestamp()))
            d_end = min(end_time, int(d_end_dt.timestamp()))
            is_full = d_start == int(d_start_dt.timestamp()) and d_end == int(d_end_dt.timestamp())

            if is_full and cur_date < now_wib.date():
                d_stat = session.scalar(
                    select(DailyStat).where(
                        DailyStat.device_id == device_id,
                        DailyStat.day == cur_date.strftime("%Y-%m-%d"),
                    )
                )
                accum_cost += int(d_stat.cost_rp) if d_stat else 0
            else:
                stmt_kwh = select(func.sum(Reading.delta_kwh)).where(
                    Reading.device_id == device_id,
                    Reading.ts >= d_start,
                    Reading.ts <= d_end,
                )
                d_kwh = float(session.scalar(stmt_kwh) or 0.0)
                if cur_date == now_wib.date():
                    t_sen = active_tariff_sen
                else:
                    d_stat = session.scalar(
                        select(DailyStat).where(
                            DailyStat.device_id == device_id,
                            DailyStat.day == cur_date.strftime("%Y-%m-%d"),
                        )
                    )
                    t_sen = d_stat.tariff_sen if d_stat else active_tariff_sen
                accum_cost += calculate_cost_rp(d_kwh, t_sen, extra_percent)

            cur_date += timedelta(days=1)
        total_cost_rp = accum_cost

    # Agregasi kwh, daya rata-rata, dan puncak dari readings
    stmt_stats = select(
        func.sum(Reading.delta_kwh),
        func.avg(Reading.p),
        func.max(Reading.p),
    ).where(
        Reading.device_id == device_id,
        Reading.ts >= start_time,
        Reading.ts <= end_time,
    )
    stat_row = session.execute(stmt_stats).one()
    total_kwh = round(float(stat_row[0] or 0.0), 3)
    avg_power_w = round(float(stat_row[1] or 0.0), 1)
    peak_w = round(float(stat_row[2] or 0.0), 1)

    peak_ts: Optional[int] = None
    if peak_w > 0.0:
        peak_ts = session.scalar(
            select(Reading.ts)
            .where(
                Reading.device_id == device_id,
                Reading.ts >= start_time,
                Reading.ts <= end_time,
                Reading.p == peak_w,
            )
            .order_by(Reading.ts.asc())
            .limit(1)
        )

    return {
        "device_id": device_id,
        "from": start_time,
        "to": end_time,
        "kwh": total_kwh,
        "cost_rp": total_cost_rp,
        "avg_power_w": avg_power_w,
        "peak_w": peak_w,
        "peak_ts": peak_ts,
        "tariff_sen": active_tariff_sen,
        "cost_estimated": cost_estimated,
    }


def calculate_device_forecast(
    session: Session, device_id: str, now_dt: Optional[datetime] = None
) -> dict[str, Any]:
    """Menghitung proyeksi kWh dan biaya akhir bulan kalender berjalan."""
    device = session.scalar(select(Device).where(Device.id == device_id))
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": 404, "message": f"Device '{device_id}' not found"}},
        )

    now_wib = now_dt.astimezone(TZ_WIB) if now_dt else datetime.now(tz=TZ_WIB)
    today_str = now_wib.strftime("%Y-%m-%d")
    current_month_prefix = now_wib.strftime("%Y-%m")

    # Ambil seluruh record hourly_stats untuk menentukan hari penuh (sampel >= 90% * 8640 = 7776)
    all_hours = session.scalars(select(HourlyStat).where(HourlyStat.device_id == device_id)).all()
    samples_per_day: dict[str, int] = {}
    for h in all_hours:
        d_str = datetime.fromtimestamp(h.hour_start, tz=TZ_WIB).strftime("%Y-%m-%d")
        samples_per_day[d_str] = samples_per_day.get(d_str, 0) + h.samples

    # Hari penuh valid: sampel >= 7776 dan hari < hari ini
    full_days = [d for d, s in samples_per_day.items() if s >= 7776 and d < today_str]
    full_days.sort(reverse=True)

    basis_days_list = full_days[:7]  # Ambil hingga 7 hari penuh terakhir
    basis_days = len(basis_days_list)

    if basis_days == 0:
        return {
            "device_id": device_id,
            "available": False,
            "basis_days": 0,
            "low_confidence": False,
            "avg_daily_kwh": None,
            "month_so_far_kwh": None,
            "month_so_far_cost_rp": None,
            "projected_kwh": None,
            "projected_cost_rp": None,
        }

    # Ambil data kwh untuk basis_days
    basis_stats = session.scalars(
        select(DailyStat).where(
            DailyStat.device_id == device_id, DailyStat.day.in_(basis_days_list)
        )
    ).all()
    avg_daily_kwh = round(sum(d.kwh for d in basis_stats) / basis_days, 3)
    low_confidence = basis_days < 3

    # Ambil data bulan ini (termasuk hari ini)
    month_stats = session.scalars(
        select(DailyStat).where(
            DailyStat.device_id == device_id, DailyStat.day.startswith(current_month_prefix)
        )
    ).all()
    month_so_far_kwh = round(sum(d.kwh for d in month_stats), 3)
    month_so_far_cost_rp = sum(d.cost_rp for d in month_stats)

    today_stat = next((d for d in month_stats if d.day == today_str), None)
    today_kwh = today_stat.kwh if today_stat else 0.0

    # Sisa hari kalender bulan ini (tidak termasuk hari ini)
    days_in_month = calendar.monthrange(now_wib.year, now_wib.month)[1]
    sisa_hari = max(0, days_in_month - now_wib.day)

    remaining_today_kwh = max(avg_daily_kwh - today_kwh, 0.0)
    projected_kwh = round(month_so_far_kwh + remaining_today_kwh + (sisa_hari * avg_daily_kwh), 3)

    active_tariff_sen = get_current_tariff_sen(session, user_id=device.owner_user_id)
    extra_percent = get_extra_percent(session, user_id=device.owner_user_id)
    projected_cost_rp = calculate_cost_rp(projected_kwh, active_tariff_sen, extra_percent)

    return {
        "device_id": device_id,
        "available": True,
        "basis_days": basis_days,
        "low_confidence": low_confidence,
        "avg_daily_kwh": avg_daily_kwh,
        "month_so_far_kwh": month_so_far_kwh,
        "month_so_far_cost_rp": month_so_far_cost_rp,
        "projected_kwh": projected_kwh,
        "projected_cost_rp": projected_cost_rp,
    }
