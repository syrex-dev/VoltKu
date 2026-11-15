import calendar
from datetime import datetime, time, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import DailyStat, Device, HourlyStat, Reading
from app.mqtt_ingest import get_device_status
from app.services.aggregation import get_current_tariff_sen, get_extra_percent
from app.services.cost import calculate_cost_rp

router = APIRouter(
    prefix="/api/devices", tags=["Devices"], dependencies=[Depends(get_current_user)]
)

TZ_WIB = ZoneInfo("Asia/Jakarta")


@router.get("", response_model=list[dict[str, Any]])
def list_devices(session: Session = Depends(get_db)):
    """Mengambil daftar perangkat terdaftar beserta status dinamis online/offline."""
    devices = session.scalars(select(Device).order_by(Device.id.asc())).all()
    now_utc = int(datetime.now(timezone.utc).timestamp())
    return [
        {
            "id": d.id,
            "name": d.name,
            "location": d.location,
            "mcb_watt": d.mcb_watt,
            "created_at": d.created_at,
            "last_seen_at": d.last_seen_at,
            "last_data_ts": d.last_data_ts,
            "status": get_device_status(d, now_utc=now_utc),
        }
        for d in devices
    ]


@router.get("/{device_id}/latest")
def get_latest_reading(device_id: str, session: Session = Depends(get_db)):
    """Mengambil data telemetri terbaru dari perangkat tertentu."""
    device = session.scalar(select(Device).where(Device.id == device_id))
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": 404, "message": f"Device '{device_id}' not found"}},
        )

    reading = session.scalar(
        select(Reading).where(Reading.device_id == device_id).order_by(Reading.ts.desc()).limit(1)
    )
    if not reading:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": 404,
                    "message": f"No telemetry readings found for device '{device_id}'",
                }
            },
        )

    return {
        "device_id": device_id,
        "ts": int(reading.ts),
        "v": reading.v,
        "i": reading.i,
        "p": reading.p,
        "e": reading.e_kwh,
        "delta_kwh": reading.delta_kwh,
        "f": reading.f,
        "pf": reading.pf,
        "rssi": reading.rssi,
        "is_gap": reading.is_gap,
    }


@router.get("/{device_id}/series")
def get_device_series(
    device_id: str,
    from_ts: Optional[int] = Query(None, alias="from"),
    to_ts: Optional[int] = Query(None, alias="to"),
    resolution: Optional[str] = Query("auto"),
    session: Session = Depends(get_db),
):
    """Mengambil deret waktu telemetri daya dengan pemilihan resolusi otomatis atau spesifik."""
    device = session.scalar(select(Device).where(Device.id == device_id))
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": 404, "message": f"Device '{device_id}' not found"}},
        )

    now_utc = int(datetime.now(timezone.utc).timestamp())
    end_time = to_ts if to_ts is not None else now_utc
    start_time = from_ts if from_ts is not None else (end_time - 86400)

    delta_sec = end_time - start_time
    if delta_sec < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {"code": 400, "message": "'from' timestamp must be <= 'to' timestamp"}
            },
        )

    res = resolution
    if res == "auto":
        if delta_sec <= 5 * 3600:
            res = "raw"
        elif delta_sec <= 3 * 86400:
            res = "5m"
        elif delta_sec <= 60 * 86400:
            res = "1h"
        else:
            res = "1d"

    points: list[dict[str, Any]] = []
    interval_seconds = 10

    if res == "raw":
        interval_seconds = 10
        stmt = (
            select(Reading.ts, Reading.p, Reading.v)
            .where(
                Reading.device_id == device_id,
                Reading.ts >= start_time,
                Reading.ts <= end_time,
            )
            .order_by(Reading.ts.asc())
        )
        rows = session.execute(stmt).all()
        for r in rows:
            points.append(
                {
                    "ts": int(r[0]),
                    "p": round(float(r[1]), 1),
                    "p_max": round(float(r[1]), 1),
                    "p_min": round(float(r[1]), 1),
                    "v": round(float(r[2]), 1),
                }
            )

    elif res == "5m":
        interval_seconds = 300
        bucket_expr = (Reading.ts / 300) * 300
        stmt = (
            select(
                bucket_expr.label("bucket_ts"),
                func.avg(Reading.p),
                func.max(Reading.p),
                func.min(Reading.p),
                func.avg(Reading.v),
            )
            .where(
                Reading.device_id == device_id,
                Reading.ts >= start_time,
                Reading.ts <= end_time,
            )
            .group_by("bucket_ts")
            .order_by("bucket_ts")
        )
        rows = session.execute(stmt).all()
        for r in rows:
            points.append(
                {
                    "ts": int(r[0]),
                    "p": round(float(r[1]), 1),
                    "p_max": round(float(r[2]), 1),
                    "p_min": round(float(r[3]), 1),
                    "v": round(float(r[4]), 1),
                }
            )

    elif res == "1h":
        interval_seconds = 3600
        stmt = (
            select(
                HourlyStat.hour_start,
                HourlyStat.p_avg,
                HourlyStat.p_max,
                HourlyStat.p_min,
            )
            .where(
                HourlyStat.device_id == device_id,
                HourlyStat.hour_start >= start_time,
                HourlyStat.hour_start <= end_time,
            )
            .order_by(HourlyStat.hour_start.asc())
        )
        rows = session.execute(stmt).all()
        for r in rows:
            points.append(
                {
                    "ts": int(r[0]),
                    "p": round(float(r[1]), 1),
                    "p_max": round(float(r[2]), 1),
                    "p_min": round(float(r[3]), 1),
                    "v": None,
                }
            )

    else:  # "1d"
        interval_seconds = 86400
        stmt = (
            select(DailyStat.day, DailyStat.kwh, DailyStat.p_max)
            .where(DailyStat.device_id == device_id)
            .order_by(DailyStat.day.asc())
        )
        rows = session.execute(stmt).all()
        for r in rows:
            d_date = datetime.strptime(r[0], "%Y-%m-%d").date()
            d_epoch = int(datetime.combine(d_date, time(0, 0, 0), tzinfo=TZ_WIB).timestamp())
            if start_time <= d_epoch <= end_time:
                # Estimasi rata-rata watt harian = kWh * 1000 / 24 jam
                avg_watt = round((float(r[1]) * 1000.0) / 24.0, 1)
                points.append(
                    {
                        "ts": d_epoch,
                        "p": avg_watt,
                        "p_max": round(float(r[2]), 1),
                        "p_min": 0.0,
                        "v": None,
                    }
                )

    truncated = len(points) > 2000
    if truncated:
        points = points[:2000]

    return {
        "device_id": device_id,
        "from": start_time,
        "to": end_time,
        "interval_seconds": interval_seconds,
        "truncated": truncated,
        "points": points,
    }


@router.get("/{device_id}/summary")
def get_device_summary(
    device_id: str,
    range: Optional[str] = Query(None),
    from_ts: Optional[int] = Query(None, alias="from"),
    to_ts: Optional[int] = Query(None, alias="to"),
    session: Session = Depends(get_db),
):
    """Rangkuman konsumsi kWh, biaya, rata-rata, dan beban puncak untuk periode tertentu."""
    device = session.scalar(select(Device).where(Device.id == device_id))
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": 404, "message": f"Device '{device_id}' not found"}},
        )

    now_wib = datetime.now(tz=TZ_WIB)
    active_tariff_sen = get_current_tariff_sen(session)
    extra_percent = get_extra_percent(session)

    if range:
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
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": 400,
                        "message": "Invalid range parameter. Use today, week, or month.",
                    }
                },
            )
    else:
        now_utc = int(datetime.now(timezone.utc).timestamp())
        end_time = to_ts if to_ts is not None else now_utc
        start_time = from_ts if from_ts is not None else (end_time - 86400)

    # Cek apakah rentang tepat mencakup hari-hari penuh yang lampau (tanpa jam parsial)
    dt_from = datetime.fromtimestamp(start_time, tz=TZ_WIB)
    dt_to = datetime.fromtimestamp(end_time, tz=TZ_WIB)

    is_exact_midnight_start = dt_from.time() == time(0, 0, 0)
    is_exact_midnight_end = dt_to.time() in (time(23, 59, 59), time(0, 0, 0))
    is_all_past_days = dt_to.date() < now_wib.date()

    cost_estimated = True
    total_cost_rp = 0

    if is_exact_midnight_start and is_exact_midnight_end and is_all_past_days:
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
        # Rentang sub-hari atau hari berjalan -> kalkulasi per jam x tarif hari itu
        cost_estimated = True
        stmt_hours = select(HourlyStat).where(
            HourlyStat.device_id == device_id,
            HourlyStat.hour_start >= start_time,
            HourlyStat.hour_start <= end_time,
        )
        hours = session.scalars(stmt_hours).all()
        day_tariffs: dict[str, int] = {}

        covered_hour_starts = set()
        accum_cost = 0
        for h in hours:
            covered_hour_starts.add(h.hour_start)
            h_day = datetime.fromtimestamp(h.hour_start, tz=TZ_WIB).strftime("%Y-%m-%d")
            if h_day not in day_tariffs:
                d_stat = session.scalar(
                    select(DailyStat).where(
                        DailyStat.device_id == device_id, DailyStat.day == h_day
                    )
                )
                day_tariffs[h_day] = d_stat.tariff_sen if d_stat else active_tariff_sen
            t_sen = day_tariffs[h_day]
            h_cost = calculate_cost_rp(h.kwh, t_sen, extra_percent)
            accum_cost += h_cost

        # Tambahkan delta_kwh dari readings untuk jam yang belum masuk ke hourly_stats
        stmt_unaggregated = (
            select(
                ((Reading.ts / 3600) * 3600).label("h_start"),
                func.sum(Reading.delta_kwh).label("kwh"),
            )
            .where(
                Reading.device_id == device_id,
                Reading.ts >= start_time,
                Reading.ts <= end_time,
            )
            .group_by("h_start")
        )
        for h_start_raw, unagg_kwh in session.execute(stmt_unaggregated).all():
            h_start = int(h_start_raw) if h_start_raw is not None else 0
            if h_start not in covered_hour_starts and unagg_kwh:
                h_day = datetime.fromtimestamp(h_start, tz=TZ_WIB).strftime("%Y-%m-%d")
                if h_day not in day_tariffs:
                    d_stat = session.scalar(
                        select(DailyStat).where(
                            DailyStat.device_id == device_id, DailyStat.day == h_day
                        )
                    )
                    day_tariffs[h_day] = d_stat.tariff_sen if d_stat else active_tariff_sen
                t_sen = day_tariffs[h_day]
                accum_cost += calculate_cost_rp(float(unagg_kwh), t_sen, extra_percent)

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


@router.get("/{device_id}/forecast")
def get_device_forecast(device_id: str, session: Session = Depends(get_db)):
    """Menghitung proyeksi kWh dan biaya akhir bulan kalender berjalan."""
    device = session.scalar(select(Device).where(Device.id == device_id))
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": 404, "message": f"Device '{device_id}' not found"}},
        )

    now_wib = datetime.now(tz=TZ_WIB)
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

    active_tariff_sen = get_current_tariff_sen(session)
    extra_percent = get_extra_percent(session)
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
