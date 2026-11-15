from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db

router = APIRouter(
    prefix="/api/anomalies", tags=["Anomalies"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=list[dict[str, Any]])
def get_anomalies_endpoint(
    device_id: Optional[str] = Query(None),
    from_ts: Optional[int] = Query(None, alias="from"),
    session: Session = Depends(get_db),
):
    """Mengembalikan daftar anomali (kosong sebelum integrasi Milestone M3)."""
    return []
