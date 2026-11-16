import json
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Anomaly

router = APIRouter(
    prefix="/api/anomalies", tags=["Anomalies"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=list[dict[str, Any]])
def get_anomalies_endpoint(
    device_id: Optional[str] = Query(None),
    from_ts: Optional[int] = Query(None, alias="from"),
    session: Session = Depends(get_db),
):
    """Mengembalikan daftar anomali dari tabel anomalies (default 7 hari terakhir, terbaru dulu)."""
    now_ts = int(time.time())
    if from_ts is None:
        from_ts = now_ts - (7 * 86400)

    stmt = select(Anomaly).where(Anomaly.ts >= from_ts)
    if device_id:
        stmt = stmt.where(Anomaly.device_id == device_id)
    stmt = stmt.order_by(Anomaly.ts.desc())

    anomalies = session.scalars(stmt).all()
    results = []
    for a in anomalies:
        try:
            details = json.loads(a.details_json) if a.details_json else {}
        except Exception:
            details = {"raw": a.details_json}

        results.append({
            "id": a.id,
            "device_id": a.device_id,
            "ts": a.ts,
            "type": a.type,
            "severity": a.severity,
            "details": details,
            "message": a.message,
            "notified": bool(a.notified),
        })

    return results
