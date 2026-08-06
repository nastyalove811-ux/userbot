"""
Модуль PingBot — периодическая проверка доступности сторонних ботов.
Команды регистрируют/показывают список; фоновый цикл (run_pingbot_loop)
запускается воркером отдельной задачей на каждый аккаунт.
"""
from __future__ import annotations

import asyncio
import datetime as dt

from sqlalchemy import delete, select

from app.db import PingBot, async_session_factory
from app.modules.base import CommandContext, command


@command("addpingbot", module="pingbot", description="Добавить бота в мониторинг")
async def cmd_addpingbot(ctx: CommandContext) -> None:
    if len(ctx.args) < 2:
        await ctx.event.reply(f"Использование: {ctx.prefix}addpingbot <бот> <текст>")
        return
    bot_username = ctx.args[0].lstrip("@")
    ping_text = " ".join(ctx.args[1:])
    async with async_session_factory() as session:
        session.add(PingBot(account_id=ctx.account_id, bot_username=bot_username, ping_text=ping_text))
        await session.commit()
    await ctx.event.reply(f"✅ @{bot_username} добавлен в мониторинг.")


@command("delpingbot", module="pingbot", description="Удалить бота из мониторинга")
async def cmd_delpingbot(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}delpingbot <бот>")
        return
    bot_username = ctx.args[0].lstrip("@")
    async with async_session_factory() as session:
        await session.execute(
            delete(PingBot).where(PingBot.account_id == ctx.account_id, PingBot.bot_username == bot_username)
        )
        await session.commit()
    await ctx.event.reply(f"✅ @{bot_username} удалён из мониторинга.")


@command("pingbots", module="pingbot", description="Список отслеживаемых ботов")
async def cmd_pingbots(ctx: CommandContext) -> None:
    async with async_session_factory() as session:
        result = await session.execute(select(PingBot).where(PingBot.account_id == ctx.account_id))
        rows = result.scalars().all()
    if not rows:
        await ctx.event.reply("Список пуст.")
        return
    lines = ["🤖 Отслеживаемые боты:"]
    for row in rows:
        status = "🟢 онлайн" if row.is_online else ("🔴 офлайн" if row.is_online is False else "⚪ неизвестно")
        lines.append(f"• @{row.bot_username} — {status}")
    await ctx.event.reply("\n".join(lines))


async def _check_bot(client, row: PingBot) -> bool:
    try:
        async with client.conversation(row.bot_username, timeout=row.timeout_seconds) as conv:
            await conv.send_message(row.ping_text)
            await conv.get_response()
            return True
    except asyncio.TimeoutError:
        return False
    except Exception:  # noqa: BLE001
        return False


@command("pingnow", module="pingbot", description="Ручная проверка всех ботов")
async def cmd_pingnow(ctx: CommandContext) -> None:
    async with async_session_factory() as session:
        result = await session.execute(select(PingBot).where(PingBot.account_id == ctx.account_id))
        rows = result.scalars().all()
    if not rows:
        await ctx.event.reply("Список пуст.")
        return

    lines = ["📡 Результаты проверки:"]
    for row in rows:
        online = await _check_bot(ctx.client, row)
        lines.append(f"• @{row.bot_username} — {'🟢 онлайн' if online else '🔴 офлайн'}")
        async with async_session_factory() as session:
            db_row = await session.get(PingBot, row.id)
            if db_row:
                db_row.is_online = online
                await session.commit()
    await ctx.event.reply("\n".join(lines))


async def run_pingbot_loop(account_id: int, client) -> None:
    """Фоновый цикл, запускается воркером как asyncio.Task на каждый аккаунт."""
    while True:
        async with async_session_factory() as session:
            result = await session.execute(select(PingBot).where(PingBot.account_id == account_id))
            rows = result.scalars().all()

        for row in rows:
            online = await _check_bot(client, row)
            was_online = row.is_online
            async with async_session_factory() as session:
                db_row = await session.get(PingBot, row.id)
                if db_row:
                    db_row.is_online = online
                    await session.commit()
            if was_online and not online:
                try:
                    await client.send_message("me", f"⚠️ Бот @{row.bot_username} не отвечает.")
                except Exception:  # noqa: BLE001
                    pass
            await asyncio.sleep(1)  # небольшая пауза между проверками, чтобы не флудить

        # Ждём минимальный interval_seconds среди ботов (по умолчанию 300с)
        min_interval = min((r.interval_seconds for r in rows), default=300)
        await asyncio.sleep(max(min_interval, 30))
