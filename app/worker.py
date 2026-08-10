"""
Воркер — асинхронный процесс, поддерживающий Telethon-клиенты для каждого
активного аккаунта, обрабатывающий входящие команды и фоновые задачи из
очереди Redis (например, будущие модули с cron-подобной логикой: PingBot,
Streak и т.д. запускают свои периодические таски отдельно, см. modules/*).
"""
from __future__ import annotations

import asyncio
import logging
import signal

from sqlalchemy import select
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession
from telethon.tl.types import UserStatusOnline, User

from app.db import Account, BannedWord, LogEntry, async_session_factory, init_models
from app.modules import (  # noqa: F401 — импорт регистрирует команды через декоратор @command
    admin, chat, chatstats, clone, contacts, core, info, kurs,
    messagetofile, pingbot, purger, quotes, screenshot, streak,
    swmute, test, typingwatch, urldl, voicy, webshot, welcome, wordle,
)
from app.modules.base import CommandContext, PermissionDenied, all_commands, check_chat_permission, is_system_admin
from app.modules.core import get_prefix, get_setting
from app.modules.pingbot import run_pingbot_loop
from app.modules.streak import run_streak_midnight_check, update_streak_on_message
from app.modules.swmute import is_swmuted
from app.modules.typingwatch import clear_typing_marker, on_typing_event
from app.modules.voicy import handle_auto_voice
from app.modules.welcome import handle_chat_action
from app.modules.wordle import handle_guess
from app.redis_client import publish_event, subscribe_events
from app.settings import get_settings
from app.utils import decrypt, parse_command

_background_tasks: list[asyncio.Task] = []

logger = logging.getLogger("userbot.worker")

_clients: dict[int, TelegramClient] = {}
_shutdown_event = asyncio.Event()
_restart_requested = asyncio.Event()


async def request_restart() -> None:
    _restart_requested.set()


async def _log_event(account_id: int, event_type: str, chat_id: int | None, user_id: int | None, message: str, details: dict | None = None) -> None:
    async with async_session_factory() as session:
        session.add(
            LogEntry(
                account_id=account_id, event_type=event_type, chat_id=chat_id,
                user_id=user_id, message=message, details=details,
            )
        )
        await session.commit()


async def _resolve_alias(account_id: int, command_name: str) -> str:
    from sqlalchemy import select as sa_select

    from app.db import Alias

    async with async_session_factory() as session:
        result = await session.execute(
            sa_select(Alias).where(Alias.account_id == account_id, Alias.alias == command_name)
        )
        row = result.scalar_one_or_none()
        return row.command.split()[0] if row else command_name


async def _dispatch(account_id: int, client: TelegramClient, event) -> None:
    settings = get_settings()
    sender_id = event.sender_id

    text = event.raw_text or ""
    prefix = await get_prefix(account_id)
    parsed = parse_command(text, prefix)
    if parsed is None:
        return

    command_name = await _resolve_alias(account_id, parsed.command)
    spec = all_commands().get(command_name)
    if spec is None:
        return

    if spec.admin_only and not is_system_admin(sender_id):
        return  # тихо игнорируем: команды доступны только владельцу аккаунта

    ctx = CommandContext(
        client=client, event=event, account_id=account_id,
        args=parsed.args, raw_args=parsed.raw_args, prefix=prefix,
    )

    try:
        await check_chat_permission(client, event, spec.required_right)
        await spec.handler(ctx)
        await _log_event(account_id, "command", event.chat_id, sender_id, text)
    except PermissionDenied as exc:
        await event.reply(f"⛔ {exc}")
    except FloodWaitError as exc:
        logger.warning("FloodWait %s сек для аккаунта %s", exc.seconds, account_id)
        await asyncio.sleep(exc.seconds)
        try:
            await spec.handler(ctx)
        except Exception as inner_exc:  # noqa: BLE001
            logger.exception("Повторная попытка после FloodWait не удалась: %s", inner_exc)
    except Exception as exc:  # noqa: BLE001 — не роняем воркер из-за ошибки в одной команде
        logger.exception("Ошибка выполнения команды %s: %s", command_name, exc)
        try:
            await event.reply(f"❌ Ошибка выполнения команды: {exc}")
        except Exception:  # noqa: BLE001
            pass


async def _handle_incoming(account_id: int, client: TelegramClient, event) -> None:
    """Обрабатывает входящие сообщения: тихий мут, автоудаление по словам,
    авто-распознавание голосовых, огоньки, угадывание слов в Wordle."""
    chat_id = event.chat_id
    sender_id = event.sender_id

    if sender_id is None or chat_id is None:
        return

    # Тихий мут — сообщение удаляется без изменения официальных прав пользователя.
    if await is_swmuted(account_id, chat_id, sender_id):
        try:
            await event.delete()
        except Exception:  # noqa: BLE001
            pass
        return

    # Автомодерация по запрещённым словам (модуль Purger: .delword).
    if event.raw_text:
        async with async_session_factory() as session:
            result = await session.execute(
                select(BannedWord).where(BannedWord.account_id == account_id, BannedWord.chat_id == chat_id)
            )
            banned_words = [row.word for row in result.scalars().all()]
        lowered = event.raw_text.lower()
        if any(word in lowered for word in banned_words):
            try:
                await event.delete()
            except Exception:  # noqa: BLE001
                pass
            return

    if event.voice:
        await handle_auto_voice(client, account_id, event)

    chat = await event.get_chat()
    if isinstance(chat, User):
        await update_streak_on_message(account_id, chat_id, outgoing=False)

    await clear_typing_marker(account_id, chat_id, sender_id)

    if event.raw_text and not (event.raw_text.startswith(await get_prefix(account_id))):
        await handle_guess(account_id, chat_id, event)


async def _start_client_for_account(account: Account) -> TelegramClient | None:
    settings = get_settings()
    if not account.session_string:
        logger.warning("Аккаунт %s не имеет активной сессии — пропущен", account.id)
        return None

    session_str = decrypt(account.session_string)
    client = TelegramClient(StringSession(session_str), settings.api_id, settings.api_hash)

    @client.on(events.NewMessage(outgoing=True))
    async def _on_outgoing(event, _account_id=account.id, _client=client):  # noqa: ANN001
        await _dispatch(_account_id, _client, event)

    @client.on(events.NewMessage(incoming=True))
    async def _on_incoming(event, _account_id=account.id, _client=client):  # noqa: ANN001
        await _handle_incoming(_account_id, _client, event)

    @client.on(events.ChatAction)
    async def _on_chat_action(event, _account_id=account.id, _client=client):  # noqa: ANN001
        await handle_chat_action(_client, _account_id, event)

    @client.on(events.UserUpdate)
    async def _on_user_update(event, _account_id=account.id, _client=client):  # noqa: ANN001
        if getattr(event, "typing", False):
            try:
                user = await event.get_user()
                await on_typing_event(_account_id, _client, event.chat_id, event.user_id, getattr(user, "first_name", str(event.user_id)))
            except Exception:  # noqa: BLE001
                pass

    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.error("Аккаунт %s не авторизован (сессия недействительна)", account.id)
            return None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Не удалось подключить аккаунт %s: %s", account.id, exc)
        return None

    _clients[account.id] = client
    logger.info("Аккаунт %s подключён", account.id)
    return client


async def _load_active_accounts() -> list[Account]:
    async with async_session_factory() as session:
        result = await session.execute(select(Account).where(Account.is_active == True, Account.bot_enabled == True))  # noqa: E712
        return list(result.scalars().all())


async def _listen_sync_events() -> None:
    """Слушает Redis pub/sub на предмет команд от API (например, добавление аккаунта)."""
    async for event in subscribe_events():
        if _shutdown_event.is_set():
            break
        event_type = event.get("type")
        payload = event.get("payload", {})
        if event_type == "account_added":
            account_id = payload.get("account_id")
            async with async_session_factory() as session:
                account = await session.get(Account, account_id)
            if account:
                await _start_client_for_account(account)
        elif event_type == "account_removed":
            account_id = payload.get("account_id")
            client = _clients.pop(account_id, None)
            if client:
                await client.disconnect()
        elif event_type == "restart_requested":
            _restart_requested.set()


async def _graceful_shutdown() -> None:
    logger.info("Останавливаю воркер (graceful shutdown)...")
    for task in _background_tasks:
        task.cancel()
    _background_tasks.clear()
    for account_id, client in list(_clients.items()):
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001
            pass
    _clients.clear()
    logger.info("Все клиенты отключены.")


def _spawn_background_tasks() -> None:
    """Запускает фоновые циклы: мониторинг ботов (per-account) и полуночный пересчёт огоньков (глобально)."""
    for account_id, client in _clients.items():
        _background_tasks.append(asyncio.create_task(run_pingbot_loop(account_id, client)))
    _background_tasks.append(asyncio.create_task(run_streak_midnight_check()))


async def run_worker() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    await init_models()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown_event.set)

    accounts = await _load_active_accounts()
    for account in accounts:
        await _start_client_for_account(account)

    sync_task = asyncio.create_task(_listen_sync_events())
    _spawn_background_tasks()
    await publish_event("worker_started", {"accounts": len(_clients)})

    try:
        while not _shutdown_event.is_set():
            if _restart_requested.is_set():
                _restart_requested.clear()
                await _graceful_shutdown()
                accounts = await _load_active_accounts()
                for account in accounts:
                    await _start_client_for_account(account)
                _spawn_background_tasks()
            await asyncio.sleep(1)
    finally:
        sync_task.cancel()
        await _graceful_shutdown()


if __name__ == "__main__":
    asyncio.run(run_worker())
