"""
Управление аккаунтами через веб-панель: подключение нового номера (login
через Telethon с сохранением зашифрованной сессии), список, включение/
отключение, удаление.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

from app.auth import require_auth
from app.db import Account, async_session_factory
from app.redis_client import clear_login_code_state, get_login_code_state, publish_event, store_login_code_state
from app.settings import get_settings
from app.utils import encrypt

router = APIRouter(dependencies=[Depends(require_auth)])


class AccountOut(BaseModel):
    id: int
    phone: str
    is_active: bool
    bot_enabled: bool
    first_name: str | None
    username: str | None

    class Config:
        from_attributes = True


class SendCodeRequest(BaseModel):
    phone: str


class ConfirmCodeRequest(BaseModel):
    phone: str
    code: str
    password: str | None = None  # для аккаунтов с 2FA


@router.get("", response_model=list[AccountOut])
async def list_accounts() -> list[AccountOut]:
    async with async_session_factory() as session:
        result = await session.execute(select(Account))
        return [AccountOut.model_validate(a) for a in result.scalars().all()]


@router.post("/send-code")
async def send_code(payload: SendCodeRequest) -> dict:
    settings = get_settings()
    client = TelegramClient(StringSession(), settings.api_id, settings.api_hash)
    await client.connect()
    sent = await client.send_code_request(payload.phone)
    await store_login_code_state(
        payload.phone,
        {"session": client.session.save(), "phone_code_hash": sent.phone_code_hash},
    )
    await client.disconnect()
    return {"status": "code_sent"}


@router.post("/confirm-code")
async def confirm_code(payload: ConfirmCodeRequest) -> dict:
    settings = get_settings()
    state = await get_login_code_state(payload.phone)
    if not state:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Код устарел, запросите новый")

    client = TelegramClient(StringSession(state["session"]), settings.api_id, settings.api_hash)
    await client.connect()
    try:
        await client.sign_in(
            phone=payload.phone, code=payload.code, phone_code_hash=state["phone_code_hash"]
        )
    except SessionPasswordNeededError:
        if not payload.password:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Требуется пароль двухфакторной аутентификации")
        await client.sign_in(password=payload.password)

    me = await client.get_me()
    session_string = client.session.save()
    await client.disconnect()
    await clear_login_code_state(payload.phone)

    async with async_session_factory() as session:
        account = Account(
            phone=payload.phone,
            session_string=encrypt(session_string),
            is_active=True,
            bot_enabled=True,
            first_name=me.first_name,
            last_name=me.last_name,
            username=me.username,
            user_id=me.id,
            premium=getattr(me, "premium", False),
        )
        session.add(account)
        await session.commit()
        await session.refresh(account)

    await publish_event("account_added", {"account_id": account.id})
    return {"status": "ok", "account_id": account.id}


@router.post("/{account_id}/toggle")
async def toggle_account(account_id: int) -> dict:
    async with async_session_factory() as session:
        account = await session.get(Account, account_id)
        if not account:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Аккаунт не найден")
        account.bot_enabled = not account.bot_enabled
        await session.commit()
        enabled = account.bot_enabled

    await publish_event("account_added" if enabled else "account_removed", {"account_id": account_id})
    return {"bot_enabled": enabled}


@router.delete("/{account_id}")
async def delete_account(account_id: int) -> dict:
    async with async_session_factory() as session:
        account = await session.get(Account, account_id)
        if not account:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Аккаунт не найден")
        await session.delete(account)
        await session.commit()

    await publish_event("account_removed", {"account_id": account_id})
    return {"status": "deleted"}
