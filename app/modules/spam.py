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
    """Рассылка сообщения в текущий чат один раз"""
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}spam <сообщение>")
        return
    
    message = " ".join(ctx.args)
    await ctx.event.respond(message)
    await ctx.event.delete()  # Удалить оригинальную команду


@command(
    "cspam",
    module="spam",
    description="Отправить команду многократно (command spam)",
    admin_only=False,
)
async def cmd_cspam(ctx: CommandContext) -> None:
    """Многократно отправить одну и ту же команду/сообщение"""
    if len(ctx.args) < 2:
        await ctx.event.reply(f"Использование: {ctx.prefix}cspam <количество> <команда>")
        return
    
    try:
        count = int(ctx.args[0])
    except ValueError:
        await ctx.event.reply("Первый аргумент должен быть числом")
        return
    
    if count > 100:
        await ctx.event.reply("⚠️ Максимум 100 сообщений за раз")
        return
    
    command_text = " ".join(ctx.args[1:])
    sent_count = 0
    
    try:
        for i in range(count):
            await ctx.event.respond(command_text)
            sent_count += 1
            if i < count - 1:
                await asyncio.sleep(0.3)  # Задержка между сообщениями
    except Exception as e:
        await ctx.event.reply(f"❌ Ошибка на {sent_count+1}/{count}: {str(e)}")
        return
    
    await ctx.event.reply(f"✅ Отправлено {sent_count}/{count} сообщений")
    await ctx.event.delete()


@command(
    "wspam",
    module="spam",
    description="Отправить сообщение с вебхуком (webhook spam)",
    admin_only=False,
)
async def cmd_wspam(ctx: CommandContext) -> None:
    """Рассылка с форматированием через вебхук"""
    if len(ctx.args) < 2:
        await ctx.event.reply(f"Использование: {ctx.prefix}wspam <формат> <сообщение>")
        await ctx.event.reply("Форматы: bold, italic, code, link")
        return
    
    fmt = ctx.args[0].lower()
    message = " ".join(ctx.args[1:])
    
    if fmt == "bold":
        formatted = f"**{message}**"
    elif fmt == "italic":
        formatted = f"__{message}__"
    elif fmt == "code":
        formatted = f"`{message}`"
    elif fmt == "link" and len(ctx.args) >= 3:
        url = ctx.args[1]
        text = " ".join(ctx.args[2:])
        formatted = f"[{text}]({url})"
    else:
        await ctx.event.reply("❌ Неизвестный формат")
        return
    
    try:
        await ctx.event.respond(formatted)
        await ctx.event.reply(f"✅ Отправлено с форматом: {fmt}")
    except Exception as e:
        await ctx.event.reply(f"❌ Ошибка: {str(e)}")
    
    await ctx.event.delete()


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
    
    if count > 100:
        await ctx.event.reply("⚠️ Максимум 100 сообщений")
        return
    
    if delay < 0.3:
        delay = 0.3
        await ctx.event.reply("⚠️ Минимальная задержка 0.3 сек")
    
    message = " ".join(ctx.args[2:])
    status_msg = await ctx.event.reply(f"⏳ Рассылка {count} сообщений с задержкой {delay}сек...")
    
    for i in range(count):
        try:
            await ctx.event.respond(f"[{i+1}/{count}] {message}")
            if i < count - 1:
                await asyncio.sleep(delay)
        except Exception as e:
            await status_msg.edit(f"❌ Ошибка на сообщении {i+1}: {str(e)}")
            return
    
    await status_msg.edit(f"✅ Завершена рассылка {count} сообщений за {count * delay:.1f}сек")
    await ctx.event.delete()
