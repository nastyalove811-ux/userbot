"""
Модуль Streak — «огоньки»: подсчёт дней подряд взаимной переписки с
контактом. Обновление счётчика происходит при обработке входящих/исходящих
сообщений (см. update_streak_on_message, вызывается из worker.py) и по
cron-подобной задаче в полночь (см. run_streak_midnight_check).
"""
from __future__ import annotations

import asyncio
import datetime as dt

from sqlalchemy import select

from app.db import Streak, async_session_factory
from app.modules.base import CommandContext, command


@command("streak", module="streak", description="Включить/выключить огонёк с пользователем")
async def cmd_streak(ctx: CommandContext) -> None:
    target = None
    if ctx.args:
        target = await ctx.client.get_entity(ctx.args[0])
    else:
        chat = await ctx.event.get_chat()
        from telethon.tl.types import User
        if isinstance(chat, User):
            target = chat
    if not target:
        await ctx.event.reply(f"Использование: {ctx.prefix}streak <кто> (или в личном чате без аргументов)")
        return

    async with async_session_factory() as session:
        result = await session.execute(
            select(Streak).where(Streak.account_id == ctx.account_id, Streak.contact_id == target.id)
        )
        row = result.scalar_one_or_none()
        if row:
            await session.delete(row)
            await session.commit()
            await ctx.event.reply(f"🔥 Огонёк с {target.first_name} выключен.")
        else:
            session.add(
                Streak(
                    account_id=ctx.account_id, contact_id=target.id,
                    original_first_name=target.first_name, original_last_name=target.last_name,
                    streak_days=0, is_active=True,
                )
            )
            await session.commit()
            await ctx.event.reply(f"🔥 Огонёк с {target.first_name} включён.")


@command("streaks", module="streak", description="Показать все активные огоньки")
async def cmd_streaks(ctx: CommandContext) -> None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Streak).where(Streak.account_id == ctx.account_id, Streak.is_active == True)  # noqa: E712
        )
        rows = result.scalars().all()
    if not rows:
        await ctx.event.reply("Активных огоньков нет.")
        return
    today = dt.datetime.now(dt.timezone.utc).date()
    lines = ["🔥 Активные огоньки:"]
    for row in rows:
        wrote_today = row.last_my_message_date and row.last_my_message_date.date() == today
        lines.append(
            f"• {row.original_first_name}: {row.streak_days} дн."
            + (" ✅ сегодня" if wrote_today else " ⏳ ждём сообщение")
        )
    await ctx.event.reply("\n".join(lines))


@command("streakinfo", module="streak", description="Информация об огоньке в текущем чате")
async def cmd_streakinfo(ctx: CommandContext) -> None:
    chat = await ctx.event.get_chat()
    async with async_session_factory() as session:
        result = await session.execute(
            select(Streak).where(Streak.account_id == ctx.account_id, Streak.contact_id == chat.id)
        )
        row = result.scalar_one_or_none()
    if not row:
        await ctx.event.reply("Огонька в этом чате нет.")
        return
    await ctx.event.reply(f"🔥 Огонёк: {row.streak_days} дней подряд.")


async def update_streak_on_message(account_id: int, contact_id: int, outgoing: bool) -> None:
    """Вызывается диспетчером воркера при каждом сообщении в личном чате с активным огоньком."""
    now = dt.datetime.now(dt.timezone.utc)
    async with async_session_factory() as session:
        result = await session.execute(
            select(Streak).where(
                Streak.account_id == account_id, Streak.contact_id == contact_id, Streak.is_active == True  # noqa: E712
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            return
        if outgoing:
            row.last_my_message_date = now
        else:
            row.last_their_message_date = now
        if row.last_my_message_date and row.last_their_message_date:
            today = now.date()
            if row.last_my_message_date.date() == today and row.last_their_message_date.date() == today:
                # обе стороны написали сегодня — засчитываем, если ещё не засчитано за сегодня
                pass
        await session.commit()


async def run_streak_midnight_check() -> None:
    """Фоновая задача: раз в сутки проверяет, кто написал за прошедший день, инкрементит/сбрасывает счётчик."""
    while True:
        now = dt.datetime.now(dt.timezone.utc)
        tomorrow = (now + dt.timedelta(days=1)).replace(hour=0, minute=0, second=5, microsecond=0)
        await asyncio.sleep((tomorrow - now).total_seconds())

        yesterday = (now).date()
        async with async_session_factory() as session:
            result = await session.execute(select(Streak).where(Streak.is_active == True))  # noqa: E712
            rows = result.scalars().all()
            for row in rows:
                my_today = row.last_my_message_date and row.last_my_message_date.date() == yesterday
                their_today = row.last_their_message_date and row.last_their_message_date.date() == yesterday
                if my_today and their_today:
                    row.streak_days += 1
                else:
                    row.streak_days = 0
            await session.commit()
