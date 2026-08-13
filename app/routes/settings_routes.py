from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from app.auth import require_auth
from app.db import Setting, async_session_factory
from app.modules.core import set_setting

router = APIRouter(dependencies=[Depends(require_auth)])


class SettingOut(BaseModel):
    module: str
    key: str
    value: str | None

    class Config:
        from_attributes = True


class SettingIn(BaseModel):
    account_id: int | None
    module: str
    key: str
    value: str


@router.get("", response_model=list[SettingOut])
async def list_settings(account_id: int | None = None) -> list[SettingOut]:
    async with async_session_factory() as session:
        statement = select(Setting)
        if account_id is not None:
            statement = statement.where(Setting.account_id == account_id)
        result = await session.execute(statement)
        return [SettingOut.model_validate(s) for s in result.scalars().all()]


@router.put("")
async def update_setting(payload: SettingIn) -> dict:
    await set_setting(payload.account_id, payload.module, payload.key, payload.value)
    return {"status": "ok"}
