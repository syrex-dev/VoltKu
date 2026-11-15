import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Reading

logger = logging.getLogger(__name__)

# Pelacak penolakan berturut-turut per device: device_id -> list of e_kwh
_consecutive_rejections: dict[str, list[float]] = {}


def reset_rejection_tracker(device_id: Optional[str] = None) -> None:
    global _consecutive_rejections
    if device_id:
        _consecutive_rejections.pop(device_id, None)
    else:
        _consecutive_rejections.clear()


def calculate_delta_kwh(
    session: Session,
    device_id: str,
    ts: int,
    e_kwh: float,
    mcb_watt: int = 2200,
    publish_interval: int = 10,
) -> tuple[float, int, Optional[int]]:
    """Menghitung delta_kwh dan flag is_gap untuk telemetry baru.

    Returns:
        tuple (delta_kwh, is_gap, baseline_reading_id)
        - delta_kwh: selisih kWh (dibulatkan 3 desimal)
        - is_gap: 1 jika delta_t > 3 * publish_interval, 0 jika normal
        - baseline_reading_id: ID pembacaan yang dijadikan baseline (None jika tidak ada)
    """
    global _consecutive_rejections

    # 1. Ambil baseline langsung dari database (sampel terakhir sebelum ts)
    stmt = (
        select(Reading)
        .where(Reading.device_id == device_id, Reading.ts < ts)
        .order_by(Reading.ts.desc())
        .limit(1)
    )
    prev_reading = session.scalar(stmt)

    if prev_reading is None:
        # Sampel pertama untuk device ini di DB -> delta = 0.0
        _consecutive_rejections[device_id] = []
        return 0.0, 0, None

    dt = ts - prev_reading.ts
    dt_eff = max(dt, publish_interval)

    # Batas energi maksimum yang masuk akal: (MCB * 1.5 * dt_eff) / (3600 * 1000) kWh
    max_kwh_limit = (mcb_watt * 1.5 * dt_eff) / (3600.0 * 1000.0)

    # Gap deteksi: jika selisih waktu > 3x interval publish
    is_gap = 1 if dt > (3 * publish_interval) else 0

    rejections = _consecutive_rejections.setdefault(device_id, [])

    # Hitung energi dalam satuan integer Wh
    wh_curr = round(e_kwh * 1000)
    wh_prev = round(prev_reading.e_kwh * 1000)

    if wh_curr >= wh_prev:
        raw_delta_wh = wh_curr - wh_prev
        delta_kwh = raw_delta_wh / 1000.0

        if delta_kwh > max_kwh_limit:
            # Lonjakan tak wajar: tolak, JANGAN majukan baseline
            rejections.append(e_kwh)
            logger.warning(
                "Delta kWh %s melebihi batas wajar %s untuk device %s (dt=%ss). Penolakan ke-%s.",
                delta_kwh,
                max_kwh_limit,
                device_id,
                dt,
                len(rejections),
            )
            if len(rejections) >= 3:
                # 3 penolakan berturut-turut konsisten -> tetapkan baseline baru
                logger.warning(
                    "3 penolakan berturut-turut pada device %s. Menetapkan baseline baru.",
                    device_id,
                )
                rejections.clear()
                return 0.0, is_gap, None

            return 0.0, is_gap, prev_reading.id

        # Delta normal diterima
        rejections.clear()
        return round(delta_kwh, 3), is_gap, prev_reading.id

    else:
        # Counter reset: e_kwh turun
        delta_reset_kwh = wh_curr / 1000.0

        if delta_reset_kwh > max_kwh_limit:
            # e_baru setelah reset terlalu besar (melebihi batas wajar)
            rejections.append(e_kwh)
            logger.warning(
                "Reset counter device %s menghasilkan e_baru %s yang melebihi batas %s.",
                device_id,
                delta_reset_kwh,
                max_kwh_limit,
            )
            if len(rejections) >= 3:
                logger.warning(
                    "3 penolakan berturut-turut (reset) pada device %s. Menetapkan baseline baru.",
                    device_id,
                )
                rejections.clear()
                return 0.0, is_gap, None

            return 0.0, is_gap, prev_reading.id

        # Reset wajar diterima
        rejections.clear()
        return round(delta_reset_kwh, 3), is_gap, prev_reading.id
