from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select

from app.auth import require_auth
from app.db import Account, LogEntry, Setting, async_session_factory
from app.modules.base import all_commands, all_modules
from app.modules.core import set_setting
from app.settings import get_settings

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


class ModuleStatusOut(BaseModel):
    name: str
    enabled: bool
    commands: list[str]
    command_count: int


class ProfileOut(BaseModel):
    admin_login: str
    admin_id: int
    default_prefix: str
    default_lang: str
    total_accounts: int
    active_accounts: int
    total_logs: int
    total_settings: int
    module_count: int


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


@router.get("/modules", response_model=list[ModuleStatusOut])
async def list_modules(account_id: int | None = None) -> list[ModuleStatusOut]:
    settings = get_settings()
    available = all_modules()

    async with async_session_factory() as session:
        rows = await session.execute(select(Setting).where(Setting.account_id == account_id))
        setting_map = {f"{row.module}:{row.key}": row.value for row in rows.scalars().all()}

    result: list[ModuleStatusOut] = []
    for module_name, commands in sorted(available.items()):
        key = f"core:module_enabled:{module_name}"
        enabled_raw = setting_map.get(key)
        enabled = enabled_raw != "0" if enabled_raw is not None else True
        result.append(
            ModuleStatusOut(
                name=module_name,
                enabled=enabled,
                commands=sorted(commands),
                command_count=len(commands),
            )
        )

    if not result:
        result.append(ModuleStatusOut(name="core", enabled=True, commands=sorted(all_commands().keys()), command_count=len(all_commands())))

    return result


@router.post("/modules/{module_name}/toggle")
async def toggle_module(module_name: str, account_id: int | None = None) -> dict:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Setting).where(
                Setting.account_id == account_id,
                Setting.module == "core",
                Setting.key == f"module_enabled:{module_name}",
            )
        )
        row = result.scalar_one_or_none()
        next_value = "0" if (row and row.value == "1") else "1"
        if row:
            row.value = next_value
        else:
            session.add(Setting(account_id=account_id, module="core", key=f"module_enabled:{module_name}", value=next_value))
        await session.commit()
    return {"status": "ok", "module": module_name, "enabled": next_value == "1"}


@router.get("/profile", response_model=ProfileOut)
async def get_profile() -> ProfileOut:
    settings = get_settings()
    async with async_session_factory() as session:
        total_accounts = await session.scalar(select(func.count(Account.id))) or 0
        active_accounts = await session.scalar(
            select(func.count(Account.id)).where(Account.is_active.is_(True), Account.bot_enabled.is_(True))
        ) or 0
        total_logs = await session.scalar(select(func.count(LogEntry.id))) or 0
        total_settings = await session.scalar(select(func.count(Setting.id))) or 0

    return ProfileOut(
        admin_login=settings.admin_login,
        admin_id=settings.admin_id,
        default_prefix=settings.default_prefix,
        default_lang=settings.default_lang,
        total_accounts=int(total_accounts),
        active_accounts=int(active_accounts),
        total_logs=int(total_logs),
        total_settings=int(total_settings),
        module_count=len(all_modules()),
    )
