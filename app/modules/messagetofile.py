"""
Модуль MessageToFile — конвертация текста в файл и обратно.
"""
from __future__ import annotations

import os
import tempfile

from app.modules.base import CommandContext, command


@command("mtf", module="messagetofile", description="Сохранить текст в файл и отправить")
async def cmd_mtf(ctx: CommandContext) -> None:
    reply = await ctx.event.get_reply_message()
    text = (reply.message if reply else None) or ctx.raw_args
    if not text:
        await ctx.event.reply(f"Использование: ответом на сообщение или {ctx.prefix}mtf <текст>")
        return

    filename = (ctx.args[0] if reply and ctx.args else "message") + ".txt"
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        await ctx.client.send_file(await ctx.event.get_chat(), path, caption=f"📄 {filename}")


@command("ftm", module="messagetofile", description="Извлечь текст из прикреплённого файла")
async def cmd_ftm(ctx: CommandContext) -> None:
    reply = await ctx.event.get_reply_message()
    if not reply or not reply.document:
        await ctx.event.reply(f"Использование: ответом на файл — {ctx.prefix}ftm [код]")
        return

    data = await ctx.client.download_media(reply.document, file=bytes)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        await ctx.event.reply("❌ Не удалось прочитать файл как текст (не UTF-8).")
        return

    if ctx.args:
        text = f"```\n{text}\n```"

    if len(text) > 4000:
        text = text[:4000] + "\n... (обрезано)"
    await ctx.event.reply(text)
