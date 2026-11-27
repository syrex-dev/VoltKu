import json
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Anomaly, Device, User
from app.services.app_config import get_app_config_map
from app.services.plans import resolve_user_plan

router = APIRouter(
    prefix="/api/anomalies", tags=["Anomalies"], dependencies=[Depends(get_current_user)]
)

ADVANCED_ANOMALY_TYPES = ("l2_spike", "l3_baseload")


def query_anomalies_list(
    session: Session,
    device_id: Optional[str] = None,
    from_ts: Optional[int] = None,
    severity: Optional[str] = None,
    limit: Optional[int] = None,
    owner_user_id: Optional[int] = None,
    public_demo_only: bool = False,
    exclude_types: Optional[tuple[str, ...]] = None,
) -> list[dict[str, Any]]:
    """Query helper riwayat anomali terbaru dengan isolasi tenant / demo publik."""
    now_ts = int(time.time())
    effective_from = from_ts if from_ts is not None else now_ts - (7 * 86400)

    stmt = select(Anomaly).where(Anomaly.ts >= effective_from)
    if public_demo_only:
        demo_ids = select(Device.id).where(Device.is_public_demo == 1)
        stmt = stmt.where(Anomaly.device_id.in_(demo_ids))
    elif owner_user_id is not None:
        owned_ids = select(Device.id).where(Device.owner_user_id == owner_user_id)
        stmt = stmt.where(Anomaly.device_id.in_(owned_ids))

    if device_id:
        stmt = stmt.where(Anomaly.device_id == device_id)
    if severity:
        stmt = stmt.where(Anomaly.severity == severity.strip().lower())
    if exclude_types:
        stmt = stmt.where(Anomaly.type.not_in(exclude_types))
    stmt = stmt.order_by(Anomaly.ts.desc())
    if limit is not None and limit > 0:
        stmt = stmt.limit(limit)

    anomalies = session.scalars(stmt).all()
    results = []
    for a in anomalies:
        try:
            details = json.loads(a.details_json) if a.details_json else {}
        except Exception:
            details = {"raw": a.details_json}

        results.append(
            {
                "id": a.id,
                "device_id": a.device_id,
                "ts": a.ts,
                "type": a.type,
                "severity": a.severity,
                "details": details,
                "message": a.message,
                "notified": bool(a.notified),
            }
        )

    return results


@router.get("", response_model=list[dict[str, Any]])
def get_anomalies_endpoint(
    device_id: Optional[str] = Query(None),
    from_ts: Optional[int] = Query(None, alias="from"),
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    """Mengembalikan daftar anomali (terbatas pada perangkat user & fitur anomaly_advanced)."""
    uid = current.get("user_id") if current.get("role") == "user" else None
    exclude_types: Optional[tuple[str, ...]] = None
    if uid is not None:
        user_obj = session.get(User, int(uid))
        if user_obj:
            plan = resolve_user_plan(session, user_obj, get_app_config_map(session))
            if plan["freemium_enabled"] and not plan["limits"].get("anomaly_advanced", False):
                exclude_types = ADVANCED_ANOMALY_TYPES
    return query_anomalies_list(
        session=session,
        device_id=device_id,
        from_ts=from_ts,
        owner_user_id=uid,
        exclude_types=exclude_types,
    )
