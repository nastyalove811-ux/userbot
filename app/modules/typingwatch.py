"""
Модуль TypingWatch — отслеживает событие "печатает" в чате и уведомляет,
если человек начал печатать, но не отправил сообщение за таймаут.
Состояние хранится в Redis (typingwatch:{account_id}:{chat_id}:{user_id}).
"""
from __future__ import annotations

import asyncio
import datetime as dt

from app.modules.base import CommandContext, command
from app.modules.core import get_setting, set_setting
from app.redis_client import cache_delete, cache_get, cache_set

DEFAULT_TIMEOUT = 30


@command("typingwatch", module="typingwatch", description="Включить/выключить слежку за печатанием")
async def cmd_typingwatch(ctx: CommandContext) -> None:
    chat = await ctx.event.get_chat()
    current = await get_setting(ctx.account_id, "typingwatch", f"enabled:{chat.id}", "0")
    new_value = "0" if current == "1" else "1"
    await set_setting(ctx.account_id, "typingwatch", f"enabled:{chat.id}", new_value)
    await ctx.event.reply("👀 Слежка за печатанием " + ("включена." if new_value == "1" else "выключена."))


@command("typingstat", module="typingwatch", description="Показать, кто печатает сейчас")
async def cmd_typingstat(ctx: CommandContext) -> None:
    chat = await ctx.event.get_chat()
    key = f"typingwatch:active:{ctx.account_id}:{chat.id}"
    active = await cache_get(key)
    if not active:
        await ctx.event.reply("Сейчас никто не печатает.")
        return
    await ctx.event.reply(f"⌨️ Сейчас печатает: {active}")


async def on_typing_event(account_id: int, client, chat_id: int, user_id: int, user_name: str) -> None:
    """Вызывается воркером на событие UserUpdate (typing action)."""
    enabled = await get_setting(account_id, "typingwatch", f"enabled:{chat_id}", "0")
    if enabled != "1":
        return

    await cache_set(f"typingwatch:active:{account_id}:{chat_id}", user_name, ttl_seconds=15)

    timeout = int(await get_setting(account_id, "typingwatch", "timeout", str(DEFAULT_TIMEOUT)))
    marker_key = f"typingwatch:pending:{account_id}:{chat_id}:{user_id}"
    if await cache_get(marker_key):
        return  # уже отслеживаем этот эпизод печати

    await cache_set(marker_key, "1", ttl_seconds=timeout)
    asyncio.create_task(_check_timeout(account_id, client, chat_id, user_id, user_name, timeout, marker_key))


async def _check_timeout(account_id, client, chat_id, user_id, user_name, timeout, marker_key) -> None:
    await asyncio.sleep(timeout)
    if await cache_get(marker_key):
        try:
            await client.send_message(
                "me", f"⌨️ {user_name} печатал(а) в чате {chat_id}, но не отправил(а) сообщение за {timeout} сек."
            )
        except Exception:  # noqa: BLE001
            pass
    await cache_delete(marker_key)


async def clear_typing_marker(account_id: int, chat_id: int, user_id: int) -> None:
    """Вызывается воркером, когда пользователь всё же отправил сообщение."""
    await cache_delete(f"typingwatch:pending:{account_id}:{chat_id}:{user_id}")
