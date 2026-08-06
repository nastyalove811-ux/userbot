"""
Модуль Info — справочная информация об аккаунте, пользователях и чатах.
"""
from __future__ import annotations

from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import Channel, Chat

from app.modules.base import CommandContext, command
from app.modules.core import get_lang, get_prefix

USERBOT_VERSION = "1.0.0"


@command("info", module="info", description="Баннер: владелец, версия, модули, статус")
async def cmd_info(ctx: CommandContext) -> None:
    from app.modules.base import all_modules

    me = await ctx.client.get_me()
    prefix = await get_prefix(ctx.account_id)
    lang = await get_lang(ctx.account_id)
    modules = sorted(all_modules().keys())
    text = (
        f"🧠 Userbot v{USERBOT_VERSION}\n"
        f"👤 Владелец: {me.first_name} (id{me.id})\n"
        f"🔤 Префикс: {prefix}\n"
        f"🌐 Язык: {lang}\n"
        f"📦 Модулей загружено: {len(modules)}"
    )
    await ctx.event.reply(text)


@command("who", module="info", admin_only=True, description="Полная информация о пользователе")
async def cmd_who(ctx: CommandContext) -> None:
    reply = await ctx.event.get_reply_message()
    if ctx.args:
        user = await ctx.client.get_entity(ctx.args[0])
    elif reply:
        user = await ctx.client.get_entity(reply.sender_id)
    else:
        user = await ctx.event.get_sender()

    full = await ctx.client(GetFullUserRequest(user))
    lines = [
        f"👤 {user.first_name or ''} {user.last_name or ''}".strip(),
        f"🆔 ID: {user.id}",
        f"🔗 Username: @{user.username}" if user.username else "🔗 Username: —",
        f"📱 Телефон: {user.phone}" if getattr(user, 'phone', None) else "📱 Телефон: скрыт",
        f"⭐ Premium: {'да' if getattr(user, 'premium', False) else 'нет'}",
        f"📝 О себе: {full.full_user.about}" if full.full_user.about else "📝 О себе: —",
    ]
    await ctx.event.reply("\n".join(lines))


@command("chatinfo", module="info", description="Информация о чате")
async def cmd_chatinfo(ctx: CommandContext) -> None:
    if ctx.args:
        chat = await ctx.client.get_entity(ctx.args[0])
    else:
        chat = await ctx.event.get_chat()

    lines = [f"💬 {getattr(chat, 'title', 'Личный чат')}", f"🆔 ID: {chat.id}"]

    if isinstance(chat, Channel):
        full = await ctx.client(GetFullChannelRequest(chat))
        lines.append(f"👥 Участников: {full.full_chat.participants_count}")
        if full.full_chat.about:
            lines.append(f"📝 Описание: {full.full_chat.about}")
        lines.append(f"📢 Тип: {'канал' if chat.broadcast else 'супергруппа'}")
    elif isinstance(chat, Chat):
        lines.append(f"👥 Участников: {chat.participants_count}")
        lines.append("📢 Тип: обычная группа")

    await ctx.event.reply("\n".join(lines))
