import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.chat_service import handle_chat_query
from app.auth import get_current_user
from app.db import get_db
from app.models import ChatLog

router = APIRouter(
    prefix="/api/chat", tags=["AI Chat"], dependencies=[Depends(get_current_user)]
)


class ChatAskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


def _chat_identity(current: dict[str, Any]) -> tuple[int, str, int | None, bool]:
    role = current.get("role", "admin")
    if role == "user" and current.get("user_id") is not None:
        uid = int(current["user_id"])
        return uid, f"web_user_{uid}", uid, False
    return 0, f"web_admin_{current.get('sub', 'admin')}", None, True


@router.post("")
async def ask_ai_assistant(
    req: ChatAskRequest,
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    chat_id, rate_key, user_id, is_admin = _chat_identity(current)
    result = await handle_chat_query(
        session,
        question=req.question,
        chat_id=chat_id,
        rate_key=rate_key,
        user_id=user_id,
        is_admin=is_admin,
    )
    if result.rate_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {"code": 429, "message": result.answer}},
        )
    return {
        "answer": result.answer,
        "tools_used": result.tools_used,
        "tokens": result.tokens,
        "fallback_used": result.fallback_used,
    }


@router.get("/history")
async def get_chat_history(
    limit: int = 20,
    current: dict[str, Any] = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    chat_id, _, _, _ = _chat_identity(current)
    safe_limit = min(max(1, limit), 50)
    rows = session.scalars(
        select(ChatLog)
        .where(ChatLog.chat_id == chat_id)
        .order_by(ChatLog.ts.desc(), ChatLog.id.desc())
        .limit(safe_limit)
    ).all()
    items = []
    for r in reversed(rows):
        try:
            tools = json.loads(r.tools_used) if r.tools_used else []
        except Exception:
            tools = []
        items.append(
            {
                "id": r.id,
                "ts": r.ts,
                "question": r.question,
                "answer": r.answer,
                "tools_used": tools,
            }
        )
    return items

