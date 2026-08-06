"""
Модуль Admin — команды администрирования чата. Все команды требуют, чтобы
аккаунт обладал соответствующим правом администратора в конкретном чате;
это проверяется диспетчером через required_right перед вызовом обработчика.
"""
from __future__ import annotations

import re

from telethon.tl.functions.channels import EditAdminRequest, EditBannedRequest
from telethon.tl.functions.messages import (
    EditChatAdminRequest,
    UpdatePinnedMessageRequest,
)
from telethon.tl.types import ChatAdminRights, ChatBannedRights

from app.modules.base import CommandContext, command

_PROMOTE_LEVELS = {
    "min": ChatAdminRights(other=True),
    "medium": ChatAdminRights(
        change_info=True, delete_messages=True, ban_users=False,
        invite_users=True, pin_messages=True, manage_call=True, other=True,
    ),
    "full": ChatAdminRights(
        change_info=True, post_messages=True, edit_messages=True, delete_messages=True,
        ban_users=True, invite_users=True, pin_messages=True, add_admins=True,
        manage_call=True, anonymous=False, other=True,
    ),
}

_DURATION_RE = re.compile(r"(\d+)([dhm])")


def _parse_duration_seconds(text: str) -> int:
    total = 0
    for value, unit in _DURATION_RE.findall(text):
        value = int(value)
        total += value * {"d": 86400, "h": 3600, "m": 60}[unit]
    return total


@command("promote", module="admin", required_right="add_admins", description="Назначить администратором")
async def cmd_promote(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}promote <кто> [min|medium|full] [ранг]")
        return
    chat = await ctx.event.get_chat()
    user = await ctx.client.get_entity(ctx.args[0])
    level = ctx.args[1] if len(ctx.args) > 1 and ctx.args[1] in _PROMOTE_LEVELS else "min"
    rank = " ".join(ctx.args[2:]) if len(ctx.args) > 2 else ""
    await ctx.client(EditAdminRequest(chat, user, _PROMOTE_LEVELS[level], rank))
    await ctx.event.reply(f"✅ {user.first_name} назначен(а) администратором ({level}).")


@command("demote", module="admin", required_right="add_admins", description="Снять администратора")
async def cmd_demote(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}demote <кто>")
        return
    chat = await ctx.event.get_chat()
    user = await ctx.client.get_entity(ctx.args[0])
    await ctx.client(EditAdminRequest(chat, user, ChatAdminRights(), ""))
    await ctx.event.reply(f"✅ {user.first_name} больше не администратор.")


@command("pin", module="admin", required_right="pin_messages", description="Закрепить сообщение")
async def cmd_pin(ctx: CommandContext) -> None:
    reply = await ctx.event.get_reply_message()
    if not reply:
        await ctx.event.reply(f"Использование: ответом на сообщение — {ctx.prefix}pin [loud]")
        return
    silent = not (ctx.args and ctx.args[0].lower() == "loud")
    await ctx.client.pin_message(await ctx.event.get_chat(), reply, notify=not silent)
    await ctx.event.reply("📌 Закреплено.")


@command("unpin", module="admin", required_right="pin_messages", description="Открепить сообщение(я)")
async def cmd_unpin(ctx: CommandContext) -> None:
    chat = await ctx.event.get_chat()
    if ctx.args and ctx.args[0].lower() == "all":
        await ctx.client.unpin_message(chat)
        await ctx.event.reply("📌 Все сообщения откреплены.")
        return
    reply = await ctx.event.get_reply_message()
    if not reply:
        await ctx.event.reply(f"Использование: ответом на сообщение или {ctx.prefix}unpin all")
        return
    await ctx.client.unpin_message(chat, reply)
    await ctx.event.reply("📌 Откреплено.")


@command("kick", module="admin", required_right="ban_users", description="Выгнать пользователя (может вернуться)")
async def cmd_kick(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}kick <кто> [причина]")
        return
    chat = await ctx.event.get_chat()
    user = await ctx.client.get_entity(ctx.args[0])
    await ctx.client.kick_participant(chat, user)
    await ctx.event.reply(f"✅ {user.first_name} исключён(а) из чата.")


@command("ban", module="admin", required_right="ban_users", description="Забанить навсегда")
async def cmd_ban(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}ban <кто> [причина]")
        return
    chat = await ctx.event.get_chat()
    user = await ctx.client.get_entity(ctx.args[0])
    await ctx.client(EditBannedRequest(chat, user, ChatBannedRights(until_date=None, view_messages=True)))
    await ctx.event.reply(f"🔨 {user.first_name} забанен(а) навсегда.")


@command("tban", module="admin", required_right="ban_users", description="Забанить на время")
async def cmd_tban(ctx: CommandContext) -> None:
    if len(ctx.args) < 2:
        await ctx.event.reply(f"Использование: {ctx.prefix}tban <кто> <время, напр. 2d1h>")
        return
    import datetime as dt

    chat = await ctx.event.get_chat()
    user = await ctx.client.get_entity(ctx.args[0])
    seconds = _parse_duration_seconds(ctx.args[1])
    if seconds <= 0:
        await ctx.event.reply("❌ Некорректный формат времени (пример: 2d, 1h30m).")
        return
    until = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=seconds)
    await ctx.client(EditBannedRequest(chat, user, ChatBannedRights(until_date=until, view_messages=True)))
    await ctx.event.reply(f"🔨 {user.first_name} забанен(а) до {until:%d.%m.%Y %H:%M} UTC.")


@command("unban", module="admin", required_right="ban_users", description="Снять бан")
async def cmd_unban(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}unban <кто>")
        return
    chat = await ctx.event.get_chat()
    user = await ctx.client.get_entity(ctx.args[0])
    await ctx.client(EditBannedRequest(chat, user, ChatBannedRights(until_date=None, view_messages=False)))
    await ctx.event.reply(f"✅ {user.first_name} разбанен(а).")


@command("mute", module="admin", required_right="ban_users", description="Мут (навсегда или на время)")
async def cmd_mute(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}mute <кто> [время]")
        return
    import datetime as dt

    chat = await ctx.event.get_chat()
    user = await ctx.client.get_entity(ctx.args[0])
    until = None
    if len(ctx.args) > 1:
        seconds = _parse_duration_seconds(ctx.args[1])
        if seconds > 0:
            until = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=seconds)
    await ctx.client(EditBannedRequest(chat, user, ChatBannedRights(until_date=until, send_messages=True)))
    await ctx.event.reply(f"🔇 {user.first_name} замучен(а)" + (f" до {until:%d.%m %H:%M} UTC" if until else " навсегда"))


@command("unmute", module="admin", required_right="ban_users", description="Снять мут")
async def cmd_unmute(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}unmute <кто>")
        return
    chat = await ctx.event.get_chat()
    user = await ctx.client.get_entity(ctx.args[0])
    await ctx.client(EditBannedRequest(chat, user, ChatBannedRights(until_date=None, send_messages=False)))
    await ctx.event.reply(f"🔊 {user.first_name} снова может писать.")
