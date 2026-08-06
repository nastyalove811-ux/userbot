"""
Модуль UrlDl — скачивание файлов по прямым ссылкам и отправка в чат.
.urldl — небольшие файлы в память, .urldlbig — потоково на диск.
"""
from __future__ import annotations

import os
import tempfile

import httpx

from app.modules.base import CommandContext, command

MAX_MEMORY_SIZE = 20 * 1024 * 1024  # 20 МБ
MAX_STREAM_SIZE = 500 * 1024 * 1024  # 500 МБ


@command("urldl", module="urldl", description="Скачать файлы по ссылкам (в память)")
async def cmd_urldl(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}urldl <ссылка> [ещё ссылки...]")
        return
    chat = await ctx.event.get_chat()
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for url in ctx.args:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                if len(resp.content) > MAX_MEMORY_SIZE:
                    await ctx.event.reply(f"⚠️ {url} слишком большой для .urldl, используйте .urldlbig")
                    continue
                filename = url.split("/")[-1].split("?")[0] or "file"
                await ctx.client.send_file(chat, resp.content, file_name=filename)
            except httpx.HTTPError as exc:
                await ctx.event.reply(f"❌ Не удалось скачать {url}: {exc}")


@command("urldlbig", module="urldl", description="Скачать большие файлы потоково")
async def cmd_urldlbig(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}urldlbig <ссылка> [ещё ссылки...]")
        return
    chat = await ctx.event.get_chat()
    for url in ctx.args:
        try:
            filename = url.split("/")[-1].split("?")[0] or "file"
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, filename)
                total = 0
                async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                    async with client.stream("GET", url) as resp:
                        resp.raise_for_status()
                        with open(path, "wb") as f:
                            async for chunk in resp.aiter_bytes(chunk_size=1024 * 1024):
                                total += len(chunk)
                                if total > MAX_STREAM_SIZE:
                                    raise ValueError("Файл превышает лимит 500 МБ")
                                f.write(chunk)
                await ctx.client.send_file(chat, path, file_name=filename)
        except (httpx.HTTPError, ValueError) as exc:
            await ctx.event.reply(f"❌ Не удалось скачать {url}: {exc}")
