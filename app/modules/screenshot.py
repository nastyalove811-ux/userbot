"""
Модуль Screenshot — отправляет собеседнику в ЛС шуточное уведомление вида
«вы сделали скриншот переписки» (аналог функции в некоторых мессенджерах).
Работает только в личных чатах.
"""
from __future__ import annotations

from telethon.tl.types import User

from app.modules.base import CommandContext, command


@command("screenshot", module="screenshot", description="Уведомление о скриншоте (только в ЛС)")
async def cmd_screenshot(ctx: CommandContext) -> None:
    chat = await ctx.event.get_chat()
    if not isinstance(chat, User):
        await ctx.event.reply("❌ Команда работает только в личных чатах.")
        return

    count = 1
    if ctx.args and ctx.args[0].isdigit():
        count = min(int(ctx.args[0]), 50)

    word = "скриншот" if count == 1 else "скриншотов"
    await ctx.client.send_message(chat, f"📸 Собеседник сделал {count} {word} переписки.")
