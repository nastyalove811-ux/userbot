"""
Модуль Test — диагностические команды.
"""
from __future__ import annotations

import json
import time

from app.modules.base import CommandContext, command


@command("ping", module="test", description="Измерить задержку ответа")
async def cmd_ping(ctx: CommandContext) -> None:
    start = time.perf_counter()
    msg = await ctx.event.reply("🏓 Понг...")
    elapsed_ms = (time.perf_counter() - start) * 1000
    await msg.edit(f"🏓 Понг! {elapsed_ms:.0f} мс")


@command("dump", module="test", description="Вывести все данные сообщения (JSON)")
async def cmd_dump(ctx: CommandContext) -> None:
    reply = await ctx.event.get_reply_message()
    target = reply or ctx.event
    data = target.to_dict()
    text = json.dumps(data, default=str, ensure_ascii=False, indent=2)

    if ctx.args and ctx.args[0].lower() == "file":
        path = "/tmp/dump.json"
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        await ctx.client.send_file(await ctx.event.get_chat(), path, caption="📄 dump.json")
    else:
        # Telegram ограничивает длину сообщения — обрезаем при необходимости.
        snippet = text if len(text) < 3500 else text[:3500] + "\n... (обрезано, используйте 'file')"
        await ctx.event.reply(f"```json\n{snippet}\n```")
