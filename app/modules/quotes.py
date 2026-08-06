"""
Модуль Quotes — рендер цитаты (реальной или поддельной) в изображение.
Использует Pillow; для простоты рисует однотонный фон с именем автора,
аватаром (кружком) и текстом. !file — отправить как файл, иначе как стикер.
"""
from __future__ import annotations

import io
import re

from PIL import Image, ImageDraw, ImageFont

from app.modules.base import CommandContext, command

_COLOR_NAMES = {
    "черный": "#1c1c1c", "белый": "#f5f5f5", "синий": "#1e3a8a",
    "красный": "#7f1d1d", "зеленый": "#14532d", "фиолетовый": "#4c1d95",
}


def _resolve_color(token: str | None) -> str:
    if not token:
        return "#20232a"
    token = token.lower()
    if token in _COLOR_NAMES:
        return _COLOR_NAMES[token]
    if re.fullmatch(r"#?[0-9a-f]{6}", token):
        return token if token.startswith("#") else f"#{token}"
    return "#20232a"


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _render_quote(author_name: str, text: str, avatar_bytes: bytes | None, bg_color: str) -> bytes:
    width, height = 800, 400
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    avatar_size = 120
    if avatar_bytes:
        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGB").resize((avatar_size, avatar_size))
        mask = Image.new("L", (avatar_size, avatar_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)
        img.paste(avatar, (40, 40), mask)

    name_font = _load_font(28)
    text_font = _load_font(24)
    text_x = 40 + avatar_size + 20 if avatar_bytes else 40

    draw.text((text_x, 40), author_name, font=name_font, fill="#ffffff")

    # Простой перенос текста по ширине.
    max_width = width - text_x - 40
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=text_font) > max_width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)

    y = 100
    for line in lines[:8]:
        draw.text((text_x, y), line, font=text_font, fill="#e5e5e5")
        y += 32

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@command("quote", module="quotes", description="Цитата из реальных сообщений")
async def cmd_quote(ctx: CommandContext) -> None:
    reply = await ctx.event.get_reply_message()
    if not reply:
        await ctx.event.reply(f"Использование: ответом на сообщение — {ctx.prefix}quote [кол-во] [цвет] [!file]")
        return

    count = 1
    color_token = None
    as_file = False
    for arg in ctx.args:
        if arg == "!file":
            as_file = True
        elif arg.isdigit():
            count = min(int(arg), 10)
        else:
            color_token = arg

    chat = await ctx.event.get_chat()
    messages = [reply]
    if count > 1:
        messages = list(reversed(await ctx.client.get_messages(chat, min_id=reply.id - 1, limit=count)))

    author = await reply.get_sender()
    author_name = getattr(author, "first_name", "Unknown") or "Unknown"
    text = "\n".join((m.message or "[медиа]") for m in messages)

    avatar_bytes = None
    photos = await ctx.client.get_profile_photos(author, limit=1)
    if photos:
        avatar_bytes = await ctx.client.download_media(photos[0], file=bytes)

    image_bytes = _render_quote(author_name, text, avatar_bytes, _resolve_color(color_token))
    file_obj = io.BytesIO(image_bytes)
    file_obj.name = "quote.png"

    if as_file:
        await ctx.client.send_file(chat, file_obj, caption=f"Цитата — {author_name}")
    else:
        await ctx.client.send_file(chat, file_obj, force_document=False)


@command("fakequote", module="quotes", description="Поддельная цитата с указанным автором и текстом")
async def cmd_fakequote(ctx: CommandContext) -> None:
    reply = await ctx.event.get_reply_message()
    if reply:
        author = await reply.get_sender()
        author_name = getattr(author, "first_name", "Unknown") or "Unknown"
        text = ctx.raw_args or (reply.message or "")
        avatar_bytes = None
        photos = await ctx.client.get_profile_photos(author, limit=1)
        if photos:
            avatar_bytes = await ctx.client.download_media(photos[0], file=bytes)
    else:
        if not ctx.args:
            await ctx.event.reply(f"Использование: {ctx.prefix}fakequote @user текст (или ответом на сообщение)")
            return
        author_name = ctx.args[0].lstrip("@")
        text = " ".join(ctx.args[1:])
        avatar_bytes = None

    image_bytes = _render_quote(author_name, text, avatar_bytes, "#20232a")
    file_obj = io.BytesIO(image_bytes)
    file_obj.name = "fakequote.png"
    await ctx.client.send_file(await ctx.event.get_chat(), file_obj)
