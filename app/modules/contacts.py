"""
Модуль Contacts — управление блокировками, контактами и жалобами на спам.
Списки блокировок кэшируются в Redis (blocked:{account_id}).
"""
from __future__ import annotations

from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.functions.contacts import (
    AddContactRequest,
    BlockRequest,
    DeleteContactsRequest,
    UnblockRequest,
)
from telethon.tl.types import InputReportReasonSpam

from app.modules.base import CommandContext, command
from app.redis_client import cache_delete, cache_get, cache_set


async def _refresh_blocked_cache(ctx: CommandContext) -> None:
    blocked = await ctx.client.get_blocked()
    ids = [b.id for b in blocked] if hasattr(blocked, "__iter__") else []
    await cache_set(f"blocked:{ctx.account_id}", ids, ttl_seconds=None)


async def _resolve_target(ctx: CommandContext):
    if ctx.args:
        return await ctx.client.get_entity(ctx.args[0])
    reply = await ctx.event.get_reply_message()
    if reply:
        return await ctx.client.get_entity(reply.sender_id)
    return None


@command("block", module="contacts", description="Заблокировать пользователя")
async def cmd_block(ctx: CommandContext) -> None:
    user = await _resolve_target(ctx)
    if not user:
        await ctx.event.reply(f"Использование: {ctx.prefix}block <кто> (или ответом на сообщение)")
        return
    await ctx.client(BlockRequest(user))
    await _refresh_blocked_cache(ctx)
    await ctx.event.reply(f"🚫 {user.first_name} заблокирован(а).")


@command("unblock", module="contacts", description="Разблокировать пользователя")
async def cmd_unblock(ctx: CommandContext) -> None:
    user = await _resolve_target(ctx)
    if not user:
        await ctx.event.reply(f"Использование: {ctx.prefix}unblock <кто> (или ответом на сообщение)")
        return
    await ctx.client(UnblockRequest(user))
    await _refresh_blocked_cache(ctx)
    await ctx.event.reply(f"✅ {user.first_name} разблокирован(а).")


@command("addcontact", module="contacts", description="Добавить в контакты")
async def cmd_addcontact(ctx: CommandContext) -> None:
    reply = await ctx.event.get_reply_message()
    user = await ctx.client.get_entity(ctx.args[0]) if ctx.args and not reply else None
    if reply and not user:
        user = await ctx.client.get_entity(reply.sender_id)
    if not user:
        await ctx.event.reply(f"Использование: {ctx.prefix}addcontact <кто> [имя]")
        return
    name = " ".join(ctx.args[1:]) if len(ctx.args) > 1 else (user.first_name or "")
    await ctx.client(AddContactRequest(id=user, first_name=name, last_name="", phone=""))
    await ctx.event.reply(f"✅ {name} добавлен(а) в контакты.")


@command("delcontact", module="contacts", description="Удалить из контактов")
async def cmd_delcontact(ctx: CommandContext) -> None:
    user = await _resolve_target(ctx)
    if not user:
        await ctx.event.reply(f"Использование: {ctx.prefix}delcontact <кто>")
        return
    await ctx.client(DeleteContactsRequest(id=[user]))
    await ctx.event.reply(f"✅ {user.first_name} удалён(а) из контактов.")


@command("report", module="contacts", description="Отправить жалобу на спам")
async def cmd_report(ctx: CommandContext) -> None:
    user = await _resolve_target(ctx)
    if not user:
        await ctx.event.reply(f"Использование: {ctx.prefix}report <кто> (или ответом на сообщение)")
        return
    await ctx.client(ReportPeerRequest(peer=user, reason=InputReportReasonSpam(), message="spam"))
    await ctx.event.reply(f"🚩 Жалоба на {user.first_name} отправлена.")
