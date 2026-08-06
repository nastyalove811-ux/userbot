"""
Модуль SwMute — «тихий» мут: сообщения указанного пользователя в чате
удаляются автоматически (без изменения его официальных прав в Telegram).
Требует права на удаление сообщений в чате.
"""
from __future__ import annotations

import datetime as dt
import re

from sqlalchemy import select, update

from app.db import SwMute, async_session_factory
from app.modules.base import CommandContext, command

_DURATION_RE = re.compile(r"(\d+)([dhm])")


def _parse_duration_seconds(text: str) -> int:
    total = 0
    for value, unit in _DURATION_RE.findall(text):
        total += int(value) * {"d": 86400, "h": 3600, "m": 60}[unit]
    return total


@command("swmute", module="swmute", required_right="delete_messages", description="Тихий мут пользователя")
async def cmd_swmute(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}swmute <кто> [время]")
        return
    chat = await ctx.event.get_chat()
    user = await ctx.client.get_entity(ctx.args[0])

    async with async_session_factory() as session:
        result = await session.execute(
            select(SwMute).where(
                SwMute.account_id == ctx.account_id, SwMute.chat_id == chat.id,
                SwMute.user_id == user.id, SwMute.is_active == True,  # noqa: E712
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.is_active = False
            await session.commit()
            await ctx.event.reply(f"🔊 Тихий мут для {user.first_name} снят.")
            return

        expires_at = None
        if len(ctx.args) > 1:
            seconds = _parse_duration_seconds(ctx.args[1])
            if seconds > 0:
                expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=seconds)

        session.add(
            SwMute(account_id=ctx.account_id, chat_id=chat.id, user_id=user.id, expires_at=expires_at, is_active=True)
        )
        await session.commit()
    await ctx.event.reply(f"🔇 {user.first_name} добавлен(а) в тихий мут" + (" навсегда." if not expires_at else f" до {expires_at:%d.%m %H:%M} UTC."))


@command("swmutelist", module="swmute", description="Список замученных в текущем чате")
async def cmd_swmutelist(ctx: CommandContext) -> None:
    chat = await ctx.event.get_chat()
    async with async_session_factory() as session:
        result = await session.execute(
            select(SwMute).where(SwMute.account_id == ctx.account_id, SwMute.chat_id == chat.id, SwMute.is_active == True)  # noqa: E712
        )
        rows = result.scalars().all()
    if not rows:
        await ctx.event.reply("Список пуст.")
        return
    lines = ["🔇 Замученные:"]
    for row in rows:
        user = await ctx.client.get_entity(row.user_id)
        lines.append(f"• {user.first_name}" + (f" до {row.expires_at:%d.%m %H:%M}" if row.expires_at else ""))
    await ctx.event.reply("\n".join(lines))


@command("swmuteclear", module="swmute", required_right="delete_messages", description="Снять мут со всех")
async def cmd_swmuteclear(ctx: CommandContext) -> None:
    async with async_session_factory() as session:
        if ctx.args and ctx.args[0].lower() == "all":
            await session.execute(update(SwMute).where(SwMute.account_id == ctx.account_id).values(is_active=False))
        else:
            chat = await ctx.event.get_chat()
            await session.execute(
                update(SwMute)
                .where(SwMute.account_id == ctx.account_id, SwMute.chat_id == chat.id)
                .values(is_active=False)
            )
        await session.commit()
    await ctx.event.reply("✅ Тихий мут снят.")


async def is_swmuted(account_id: int, chat_id: int, user_id: int) -> bool:
    """Вызывается диспетчером воркера при каждом входящем сообщении в отслеживаемых чатах."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(SwMute).where(
                SwMute.account_id == account_id, SwMute.chat_id == chat_id,
                SwMute.user_id == user_id, SwMute.is_active == True,  # noqa: E712
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            return False
        if row.expires_at and row.expires_at < dt.datetime.now(dt.timezone.utc):
            row.is_active = False
            await session.commit()
            return False
        return True
