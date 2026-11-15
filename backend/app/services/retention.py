import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Reading

logger = logging.getLogger(__name__)
TZ_WIB = ZoneInfo("Asia/Jakarta")


def get_retention_cutoff_ts(now_ts: Optional[int] = None) -> int:
    """Mengembalikan cutoff timestamp retensi (00:00:00 WIB, 14 hari penuh sebelum hari ini).

    Data readings dengan ts < cutoff_ts (hari penuh yang lebih tua dari 14 hari lampau)
    menjadi target pembersihan retensi.
    """
    now_dt = (
        datetime.fromtimestamp(now_ts, tz=TZ_WIB)
        if now_ts is not None
        else datetime.now(TZ_WIB)
    )
    cutoff_date = now_dt.date() - timedelta(days=14)
    cutoff_dt = datetime(
        cutoff_date.year, cutoff_date.month, cutoff_date.day, 0, 0, 0, tzinfo=TZ_WIB
    )
    return int(cutoff_dt.timestamp())


def clean_old_readings(session: Session, cutoff_ts: int, batch_size: int = 5000) -> int:
    """Menghapus data readings yang lebih tua dari cutoff_ts per batch.

    Aturan:
    - Hanya menghapus hari penuh > 14 hari (ts < cutoff_ts).
    - JANGAN menghapus sampel terakhir tiap perangkat (max ts per device).
    - hourly_stats dan daily_stats TIDAK disentuh/dihapus (sesuai BE-05).
    """
    # 1. Cari ID sampel terakhir untuk setiap perangkat agar tidak terhapus
    subq = (
        select(Reading.device_id, func.max(Reading.ts).label("max_ts"))
        .group_by(Reading.device_id)
        .subquery()
    )
    last_sample_ids_query = select(Reading.id).join(
        subq,
        (Reading.device_id == subq.c.device_id) & (Reading.ts == subq.c.max_ts),
    )
    last_sample_ids = set(session.scalars(last_sample_ids_query).all())

    total_deleted = 0
    while True:
        # Ambil batch reading id yang lebih tua dari cutoff
        stmt = (
            select(Reading.id)
            .where(Reading.ts < cutoff_ts)
            .order_by(Reading.id)
            .limit(batch_size)
        )
        candidate_ids = session.scalars(stmt).all()
        if not candidate_ids:
            break

        # Lindungi sampel terakhir tiap perangkat
        ids_to_delete = [rid for rid in candidate_ids if rid not in last_sample_ids]
        if not ids_to_delete:
            break

        del_stmt = select(Reading).where(Reading.id.in_(ids_to_delete))
        readings_to_delete = session.scalars(del_stmt).all()
        for r in readings_to_delete:
            session.delete(r)
        session.commit()

        total_deleted += len(ids_to_delete)
        if len(candidate_ids) < batch_size:
            break

    logger.info("Retention job: deleted %d old readings (cutoff_ts=%d)", total_deleted, cutoff_ts)
    return total_deleted


async def run_retention_job(cutoff_ts: Optional[int] = None) -> int:
    """Menjalankan pembersihan retensi data secara asinkron via to_thread."""
    if cutoff_ts is None:
        cutoff_ts = get_retention_cutoff_ts()

    def _sync_clean() -> int:
        with SessionLocal() as session:
            return clean_old_readings(session, cutoff_ts)

    return await asyncio.to_thread(_sync_clean)

