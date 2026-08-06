from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from app.auth import require_auth
from app.db import LogEntry, async_session_factory

router = APIRouter(dependencies=[Depends(require_auth)])


class LogOut(BaseModel):
    id: int
    account_id: int | None
    event_type: str
    chat_id: int | None
    user_id: int | None
    message: str | None

    class Config:
        from_attributes = True


@router.get("", response_model=list[LogOut])
async def list_logs(account_id: int | None = None, limit: int = 100) -> list[LogOut]:
    async with async_session_factory() as session:
        query = select(LogEntry).order_by(LogEntry.id.desc()).limit(limit)
        if account_id is not None:
            query = query.where(LogEntry.account_id == account_id)
        result = await session.execute(query)
        return [LogOut.model_validate(row) for row in result.scalars().all()]
