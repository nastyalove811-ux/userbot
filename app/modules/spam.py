"""
Модуль Spam — команды массовой рассылки сообщений.
Поддерживает различные типы рассылки: обычная, с командами, с вебхуками, отложенная.
"""
from __future__ import annotations

import asyncio
from typing import List

from telethon.tl.types import TypeInputPeer

from app.modules.base import CommandContext, command


@command(
    "spam",
    module="spam",
    description="Отправить сообщение в чат (spam)",
    admin_only=False,
)
async def cmd_spam(ctx: CommandContext) -> None:
    """Стандартная рассылка сообщения в текущий чат"""
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}spam <сообщение>")
        return
    
    message = " ".join(ctx.args)
    await ctx.event.respond(message)


@command(
    "cspam",
    module="spam",
    description="Отправить команду многократно (command spam)",
    admin_only=False,
)
async def cmd_cspam(ctx: CommandContext) -> None:
    """Многократно отправить одну и ту же команду"""
    if len(ctx.args) < 2:
        await ctx.event.reply(f"Использование: {ctx.prefix}cspam <количество> <команда>")
        return
    
    try:
        count = int(ctx.args[0])
    except ValueError:
        await ctx.event.reply("Первый аргумент должен быть числом")
        return
    
    command_text = " ".join(ctx.args[1:])
    
    for i in range(count):
        try:
            await ctx.event.respond(command_text)
            await asyncio.sleep(0.5)  # Избегаем лимитов Telegram
        except Exception as e:
            await ctx.event.reply(f"Ошибка при отправке {i+1}: {str(e)}")
            break


@command(
    "wspam",
    module="spam",
    description="Отправить сообщение с вебхуком (webhook spam)",
    admin_only=False,
)
async def cmd_wspam(ctx: CommandContext) -> None:
    """Рассылка с использованием вебхуков для интеграции"""
    if len(ctx.args) < 2:
        await ctx.event.reply(f"Использование: {ctx.prefix}wspam <webhook_url> <сообщение>")
        return
    
    webhook_url = ctx.args[0]
    message = " ".join(ctx.args[1:])
    
    # Базовая реализация - в реальном коде здесь была бы отправка на webhook
    await ctx.event.reply(f"🔗 Webhook рассылка: {webhook_url}")
    await ctx.event.reply(f"📝 Сообщение: {message}")


@command(
    "delayspam",
    module="spam",
    description="Отправить сообщение с задержкой (delayed spam)",
    admin_only=False,
)
async def cmd_delayspam(ctx: CommandContext) -> None:
    """Рассылка с задержками между сообщениями"""
    if len(ctx.args) < 3:
        await ctx.event.reply(
            f"Использование: {ctx.prefix}delayspam <количество> <задержка(сек)> <сообщение>"
        )
        return
    
    try:
        count = int(ctx.args[0])
        delay = float(ctx.args[1])
    except ValueError:
        await ctx.event.reply("Первые два аргумента должны быть числами")
        return
    
    message = " ".join(ctx.args[2:])
    
    for i in range(count):
        try:
            await ctx.event.respond(f"[{i+1}/{count}] {message}")
            if i < count - 1:  # Не ждать после последнего сообщения
                await asyncio.sleep(delay)
        except Exception as e:
            await ctx.event.reply(f"Ошибка при отправке {i+1}: {str(e)}")
            break
    
    await ctx.event.reply(f"✅ Завершена рассылка {count} сообщений")
