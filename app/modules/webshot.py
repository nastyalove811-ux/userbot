"""
Модуль WebShot — скриншот веб-страницы (через внешний API, задаётся в
настройках) и генерация изображения с подсветкой синтаксиса кода (локально,
через Pygments — внешние сервисы не требуются).
"""
from __future__ import annotations

import io

import httpx
from pygments import highlight
from pygments.formatters import ImageFormatter
from pygments.lexers import guess_lexer, guess_lexer_for_filename
from pygments.util import ClassNotFound

from app.modules.base import CommandContext, command
from app.modules.core import get_setting


@command("shot", module="webshot", description="Скриншот веб-страницы")
async def cmd_shot(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}shot <ссылка>")
        return
    url = ctx.args[0]

    api_url_template = await get_setting(ctx.account_id, "webshot", "api_url")
    if not api_url_template:
        await ctx.event.reply(
            "❌ Не настроен сервис скриншотов. Задайте: "
            f"{ctx.prefix}settings webshot api_url <шаблон с {{url}}>\n"
            "Например, публичный сервис screenshot-as-a-service с параметром url."
        )
        return

    target_url = api_url_template.replace("{url}", url)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(target_url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "image" not in content_type:
                await ctx.event.reply("❌ Сервис вернул не изображение — проверьте настройки api_url.")
                return
            await ctx.client.send_file(await ctx.event.get_chat(), resp.content, caption=f"🌐 {url}")
    except httpx.HTTPError as exc:
        await ctx.event.reply(f"❌ Не удалось сделать скриншот: {exc}")


@command("fileshot", module="webshot", description="Подсветка синтаксиса кода из файла (ответом)")
async def cmd_fileshot(ctx: CommandContext) -> None:
    reply = await ctx.event.get_reply_message()
    if not reply or not reply.document:
        await ctx.event.reply(f"Использование: ответом на файл с кодом — {ctx.prefix}fileshot")
        return

    data = await ctx.client.download_media(reply.document, file=bytes)
    try:
        code = data.decode("utf-8")
    except UnicodeDecodeError:
        await ctx.event.reply("❌ Файл не является текстовым (UTF-8).")
        return

    filename = reply.document.attributes[0].file_name if reply.document.attributes else "code.txt"
    try:
        lexer = guess_lexer_for_filename(filename, code)
    except ClassNotFound:
        try:
            lexer = guess_lexer(code)
        except ClassNotFound:
            await ctx.event.reply("❌ Не удалось определить язык программирования.")
            return

    formatter = ImageFormatter(font_size=18, line_numbers=True, style="monokai")
    image_bytes = highlight(code, lexer, formatter)
    file_obj = io.BytesIO(image_bytes)
    file_obj.name = "code.png"
    await ctx.client.send_file(await ctx.event.get_chat(), file_obj)
