from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from app.auth import require_auth
from app.db import Account, LogEntry, Setting, async_session_factory
from app.modules import (  # noqa: F401 — регистрирует команды через @command
    admin, chat, chatstats, clone, contacts, core, info, kurs,
    messagetofile, pingbot, purger, quotes, screenshot, streak,
    swmute, test, typingwatch, urldl, voicy, webshot, welcome, wordle,
)
from app.modules.base import all_commands, all_modules
from app.modules.core import set_setting
from app.settings import get_settings

router = APIRouter(dependencies=[Depends(require_auth)])


class SettingOut(BaseModel):
    account_id: int | None = None
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


class SystemOverviewOut(BaseModel):
    redis_status: str
    database_status: str
    telegram_status: str
    worker_status: str
    uptime_seconds: int
    started_at: str
    total_accounts: int
    active_accounts: int
    total_logs: int
    total_settings: int


class ServiceStatusOut(BaseModel):
    name: str
    status: str
    detail: str


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
        if account_id is None:
            rows = await session.execute(select(Setting).where(Setting.account_id.is_(None)))
        else:
            rows = await session.execute(
                select(Setting).where(or_(Setting.account_id == account_id, Setting.account_id.is_(None)))
            )

        entries = rows.scalars().all()
        merged: dict[str, str] = {}
        for row in entries:
            key = f"{row.module}:{row.key}"
            if row.account_id == account_id or row.account_id is None:
                merged[key] = row.value

    result: list[ModuleStatusOut] = []
    for module_name, commands in sorted(available.items()):
        key = f"core:module_enabled:{module_name}"
        enabled_raw = merged.get(key)
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
        if account_id is None:
            result = await session.execute(
                select(Setting).where(
                    Setting.account_id.is_(None),
                    Setting.module == "core",
                    Setting.key == f"module_enabled:{module_name}",
                )
            )
            row = result.scalar_one_or_none()
        else:
            result = await session.execute(
                select(Setting).where(
                    Setting.module == "core",
                    Setting.key == f"module_enabled:{module_name}",
                    or_(Setting.account_id == account_id, Setting.account_id.is_(None)),
                )
            )
            row = None
            for candidate in result.scalars().all():
                if candidate.account_id == account_id:
                    row = candidate
                    break
                if row is None and candidate.account_id is None:
                    row = candidate

        next_value = "0" if (row and row.value == "1") else "1"
        if row:
            row.value = next_value
        else:
            session.add(
                Setting(
                    account_id=account_id,
                    module="core",
                    key=f"module_enabled:{module_name}",
                    value=next_value,
                )
            )
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


@router.get("/overview", response_model=SystemOverviewOut)
async def get_overview() -> SystemOverviewOut:
    settings = get_settings()
    from datetime import datetime, timezone

    async with async_session_factory() as session:
        total_accounts = await session.scalar(select(func.count(Account.id))) or 0
        active_accounts = await session.scalar(
            select(func.count(Account.id)).where(Account.is_active.is_(True), Account.bot_enabled.is_(True))
        ) or 0
        total_logs = await session.scalar(select(func.count(LogEntry.id))) or 0
        total_settings = await session.scalar(select(func.count(Setting.id))) or 0

    redis_status = "online" if getattr(get_settings(), "redis_url", None) and False else "offline"
    # Поддержка локальной разработки без Redis: состояние считается offline, если сервиса нет.
    try:
        from app.redis_client import get_redis
        redis_status = "online" if get_redis() is not None else "offline"
    except Exception:
        redis_status = "offline"

    database_status = "ready" if settings.database_url else "not_configured"
    telegram_status = "configured" if settings.api_id and settings.api_hash else "not_configured"
    worker_status = "running" if settings.api_id else "idle"

    return SystemOverviewOut(
        redis_status=redis_status,
        database_status=database_status,
        telegram_status=telegram_status,
        worker_status=worker_status,
        uptime_seconds=0,
        started_at=datetime.now(timezone.utc).isoformat(),
        total_accounts=int(total_accounts),
        active_accounts=int(active_accounts),
        total_logs=int(total_logs),
        total_settings=int(total_settings),
    )


@router.get("/services", response_model=list[ServiceStatusOut])
async def get_services() -> list[ServiceStatusOut]:
    settings = get_settings()
    services: list[ServiceStatusOut] = [
        ServiceStatusOut(name="web", status="online", detail="FastAPI panel"),
        ServiceStatusOut(name="redis", status="online" if settings.redis_url else "offline", detail="cache/session layer"),
        ServiceStatusOut(name="database", status="ready", detail=settings.database_url),
        ServiceStatusOut(name="telegram_api", status="configured" if settings.api_id and settings.api_hash else "missing", detail="Telegram credentials"),
        ServiceStatusOut(name="worker", status="idle" if not settings.api_id else "ready", detail="Telethon connector"),
    ]
    return services


@router.post("/system/restart")
async def restart_system() -> dict:
    try:
        from app.worker import request_restart
        await request_restart()
        return {"status": "ok", "message": "Перезапуск воркера запрошен"}
    except Exception:
        return {"status": "ok", "message": "Воркер недоступен в текущем процессе; запустите worker отдельно"}
