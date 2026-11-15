import statistics
from datetime import datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DailyStat, HourlyStat, Reading, Setting
from app.services.cost import calculate_cost_rp

TZ_WIB = ZoneInfo("Asia/Jakarta")


def get_wib_day(ts: int) -> str:
    """Mengembalikan tanggal YYYY-MM-DD dalam zona waktu Asia/Jakarta dari timestamp UTC."""
    return datetime.fromtimestamp(ts, tz=TZ_WIB).strftime("%Y-%m-%d")


def get_current_wib_day() -> str:
    """Mengembalikan tanggal hari ini dalam WIB."""
    return datetime.now(tz=TZ_WIB).strftime("%Y-%m-%d")


def get_current_tariff_sen(session: Session) -> int:
    """Mengambil tarif aktif saat ini dari tabel settings (default 144470 sen)."""
    setting = session.scalar(select(Setting).where(Setting.key == "tariff_sen_per_kwh"))
    if setting and setting.value:
        try:
            return int(setting.value)
        except ValueError:
            pass
    return 144470


def get_extra_percent(session: Session) -> float:
    """Mengambil persentase biaya tambahan aktif dari settings."""
    setting = session.scalar(select(Setting).where(Setting.key == "extra_percent"))
    if setting and setting.value:
        try:
            return float(setting.value)
        except ValueError:
            pass
    return 0.0


def calculate_p_base_for_day(session: Session, device_id: str, day_str: str) -> Optional[float]:
    """Menghitung median daya pukul 00.00 - 05.00 WIB untuk hari tertentu.

    Bernilai None (NULL) jika hari tersebut adalah hari berjalan dan jam saat ini < 05.00 WIB.
    """
    now_wib = datetime.now(tz=TZ_WIB)
    today_wib = now_wib.strftime("%Y-%m-%d")

    # Jika hari berjalan dan belum lewat pukul 05.00 WIB -> return None
    if day_str == today_wib and now_wib.time() < time(5, 0):
        return None

    # Tentukan rentang UTC untuk 00:00:00 s.d. 05:00:00 WIB
    d = datetime.strptime(day_str, "%Y-%m-%d").date()
    start_dt = datetime.combine(d, time(0, 0, 0), tzinfo=TZ_WIB)
    end_dt = datetime.combine(d, time(5, 0, 0), tzinfo=TZ_WIB)

    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    stmt = select(Reading.p).where(
        Reading.device_id == device_id,
        Reading.ts >= start_ts,
        Reading.ts <= end_ts,
    )
    p_values = list(session.scalars(stmt).all())
    if not p_values:
        return None

    return round(float(statistics.median(p_values)), 1)


def update_hourly_stat(session: Session, device_id: str, ts: int) -> HourlyStat:
    """Menghitung ulang bucket hourly_stats untuk jam dari ts tersebut menggunakan SUM readings."""
    hour_start = (ts // 3600) * 3600
    hour_end = hour_start + 3600

    stmt = select(
        func.coalesce(func.sum(Reading.delta_kwh), 0.0).label("kwh"),
        func.coalesce(func.avg(Reading.p), 0.0).label("p_avg"),
        func.coalesce(func.max(Reading.p), 0.0).label("p_max"),
        func.coalesce(func.min(Reading.p), 0.0).label("p_min"),
        func.count(Reading.id).label("samples"),
    ).where(
        Reading.device_id == device_id,
        Reading.ts >= hour_start,
        Reading.ts < hour_end,
    )
    res = session.execute(stmt).one()

    stat = session.scalar(
        select(HourlyStat).where(
            HourlyStat.device_id == device_id,
            HourlyStat.hour_start == hour_start,
        )
    )
    if not stat:
        stat = HourlyStat(device_id=device_id, hour_start=hour_start)
        session.add(stat)

    stat.kwh = round(float(res.kwh), 3)
    stat.p_avg = round(float(res.p_avg), 1)
    stat.p_max = round(float(res.p_max), 1)
    stat.p_min = round(float(res.p_min), 1)
    stat.samples = int(res.samples)

    return stat


def update_daily_stat(session: Session, device_id: str, ts: int) -> DailyStat:
    """Menghitung ulang bucket daily_stats untuk hari WIB dari ts tersebut (SUM readings)."""
    day_str = get_wib_day(ts)
    today_wib = get_current_wib_day()

    # Hitung batas rentang waktu UTC untuk 1 hari penuh di WIB (00:00:00 s.d. 23:59:59 WIB)
    d = datetime.strptime(day_str, "%Y-%m-%d").date()
    start_dt = datetime.combine(d, time(0, 0, 0), tzinfo=TZ_WIB)
    end_dt = datetime.combine(d, time(23, 59, 59), tzinfo=TZ_WIB)

    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    # Agregasi dari readings
    stmt = select(
        func.coalesce(func.sum(Reading.delta_kwh), 0.0).label("kwh"),
        func.coalesce(func.max(Reading.p), 0.0).label("p_max"),
    ).where(
        Reading.device_id == device_id,
        Reading.ts >= start_ts,
        Reading.ts <= end_ts,
    )
    res = session.execute(stmt).one()
    total_kwh = round(float(res.kwh), 3)
    p_max = round(float(res.p_max), 1)

    stat = session.scalar(
        select(DailyStat).where(
            DailyStat.device_id == device_id,
            DailyStat.day == day_str,
        )
    )

    if not stat:
        # Rekaman baru untuk hari ini
        tariff_sen = get_current_tariff_sen(session)
        stat = DailyStat(
            device_id=device_id,
            day=day_str,
            tariff_sen=tariff_sen,
        )
        session.add(stat)
    else:
        # Jika hari berjalan, tarif mengikuti settings terbaru; jika hari lampau, BEKUKAN tarif lama
        if day_str == today_wib:
            stat.tariff_sen = get_current_tariff_sen(session)
        # stat.tariff_sen dipertahankan untuk hari lampau!

    extra_percent = get_extra_percent(session)
    stat.kwh = total_kwh
    stat.cost_rp = calculate_cost_rp(total_kwh, stat.tariff_sen, extra_percent)
    stat.p_max = p_max
    stat.p_base = calculate_p_base_for_day(session, device_id, day_str)

    return stat
