"""
Базовый каркас для модулей юзербота.

Каждый модуль — это набор функций-обработчиков команд, зарегистрированных
через декоратор @command(). Диспетчер в worker.py находит нужный обработчик
по имени команды и вызывает его, предварительно проверив права доступа.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from telethon import TelegramClient
from telethon.tl.custom import Message
from telethon.tl.types import Channel, Chat, ChatAdminRights, User

from app.settings import get_settings

logger = logging.getLogger("userbot")

CommandHandler = Callable[["CommandContext"], Awaitable[None]]


@dataclass
class CommandContext:
    client: TelegramClient
    event: Message
    account_id: int
    args: list[str]
    raw_args: str
    prefix: str


@dataclass
class CommandSpec:
    name: str
    handler: CommandHandler
    module: str
    # Какое право нужно в чате для выполнения команды. None = не требуется (доступно
    # любому участнику), либо строка вида "delete_messages", "ban_users" и т.д.,
    # соответствующая полю telethon ChatAdminRights / participant.admin_rights.
    required_right: str | None = None
    # Требуется ли, чтобы отправитель был администратором СИСТЕМЫ (ADMIN_ID).
    # По умолчанию True — это общее правило для всех команд юзербота.
    admin_only: bool = True
    description: str = ""


_REGISTRY: dict[str, CommandSpec] = {}
_MODULES: dict[str, list[str]] = {}


def command(
    name: str,
    module: str,
    required_right: str | None = None,
    admin_only: bool = True,
    description: str = "",
):
    """Декоратор регистрации обработчика команды."""

    def decorator(func: CommandHandler) -> CommandHandler:
        spec = CommandSpec(
            name=name,
            handler=func,
            module=module,
            required_right=required_right,
            admin_only=admin_only,
            description=description,
        )
        _REGISTRY[name] = spec
        _MODULES.setdefault(module, []).append(name)
        return func

    return decorator


def get_command(name: str) -> CommandSpec | None:
    return _REGISTRY.get(name)


def all_modules() -> dict[str, list[str]]:
    return _MODULES


def all_commands() -> dict[str, CommandSpec]:
    return _REGISTRY


class PermissionDenied(Exception):
    pass


async def check_chat_permission(client: TelegramClient, event: Message, required_right: str | None) -> None:
    """
    Проверяет, что аккаунт обладает необходимым правом в текущем чате.
    Для личных чатов (User) проверка не требуется.
    """
    if required_right is None:
        return

    chat = await event.get_chat()

    if isinstance(chat, User):
        # В личных чатах административных прав не бывает — считаем разрешённым.
        return

    if isinstance(chat, Chat):
        # Обычная (не супер-) группа — права выясняются через get_permissions.
        pass

    me = await client.get_permissions(chat, "me")

    if me.is_creator:
        return

    if not getattr(me, required_right, False):
        raise PermissionDenied(
            f"Недостаточно прав в этом чате: требуется '{required_right}'."
        )


def is_system_admin(user_id: int) -> bool:
    return user_id == get_settings().admin_id
