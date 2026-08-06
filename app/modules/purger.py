"""
Модуль Purger — удаление сообщений. .delme/.delmenow не требуют прав в чате
(удаление собственных сообщений и выход доступны любому участнику), остальные
команды требуют право удаления сообщений участников; .kickall — право бана.
"""
from __future__ import annotations

from sqlalchemy import delete, select

from app.db import BannedWord, async_session_factory
from app.modules.base import CommandContext, command


@command("del", module="purger", required_right="delete_messages", description="Удалить сообщение (ответом)")
async def cmd_del(ctx: CommandContext) -> None:
    reply = await ctx.event.get_reply_message()
    if not reply:
        await ctx.event.reply(f"Использование: ответом на сообщение — {ctx.prefix}del")
        return
    await reply.delete()
    await ctx.event.delete()


@command("purge", module="purger", required_right="delete_messages", description="Удалить сообщения от ответа до команды")
async def cmd_purge(ctx: CommandContext) -> None:
    reply = await ctx.event.get_reply_message()
    if not reply:
        await ctx.event.reply(f"Использование: ответом на сообщение — {ctx.prefix}purge [кто]")
        return
    chat = await ctx.event.get_chat()
    target_user = None
    if ctx.args:
        target_user = (await ctx.client.get_entity(ctx.args[0])).id

    to_delete = []
    async for msg in ctx.client.iter_messages(chat, min_id=reply.id - 1, max_id=ctx.event.id):
        if target_user is None or msg.sender_id == target_user:
            to_delete.append(msg.id)
    if to_delete:
        await ctx.client.delete_messages(chat, to_delete)


@command("rpurge", module="purger", required_right="delete_messages", description="Удалить сообщения от начала чата до ответа")
async def cmd_rpurge(ctx: CommandContext) -> None:
    reply = await ctx.event.get_reply_message()
    if not reply:
        await ctx.event.reply(f"Использование: ответом на сообщение — {ctx.prefix}rpurge [кто]")
        return
    chat = await ctx.event.get_chat()
    target_user = None
    if ctx.args:
        target_user = (await ctx.client.get_entity(ctx.args[0])).id

    to_delete = []
    async for msg in ctx.client.iter_messages(chat, max_id=reply.id):
        if target_user is None or msg.sender_id == target_user:
            to_delete.append(msg.id)
    if to_delete:
        await ctx.client.delete_messages(chat, to_delete)
    await ctx.event.delete()


@command("delshit", module="purger", required_right="delete_messages", description="Удалить сообщения со словом")
async def cmd_delshit(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}delshit <слово>")
        return
    word = ctx.raw_args.lower()
    chat = await ctx.event.get_chat()
    to_delete = []
    async for msg in ctx.client.iter_messages(chat, search=word, limit=500):
        to_delete.append(msg.id)
    if to_delete:
        await ctx.client.delete_messages(chat, to_delete)
    await ctx.event.reply(f"🗑 Удалено сообщений: {len(to_delete)}")


@command("delme", module="purger", required_right=None, description="Удалить все свои сообщения в чате")
async def cmd_delme(ctx: CommandContext) -> None:
    chat = await ctx.event.get_chat()
    me = await ctx.client.get_me()
    to_delete = []
    async for msg in ctx.client.iter_messages(chat, from_user=me.id, limit=1000):
        to_delete.append(msg.id)
    if to_delete:
        await ctx.client.delete_messages(chat, to_delete)


@command("delmenow", module="purger", required_right=None, description="Удалить свои сообщения и покинуть чат")
async def cmd_delmenow(ctx: CommandContext) -> None:
    chat = await ctx.event.get_chat()
    me = await ctx.client.get_me()
    to_delete = []
    async for msg in ctx.client.iter_messages(chat, from_user=me.id, limit=1000):
        to_delete.append(msg.id)
    if to_delete:
        await ctx.client.delete_messages(chat, to_delete)
    await ctx.client.delete_dialog(chat)


@command("delsys", module="purger", required_right="delete_messages", description="Удалить системные сообщения")
async def cmd_delsys(ctx: CommandContext) -> None:
    from telethon.tl.types import MessageActionChatAddUser, MessageActionChatDeleteUser, MessageActionChatEditTitle

    chat = await ctx.event.get_chat()
    to_delete = []
    async for msg in ctx.client.iter_messages(chat, limit=500):
        if msg.action and isinstance(
            msg.action, (MessageActionChatAddUser, MessageActionChatDeleteUser, MessageActionChatEditTitle)
        ):
            to_delete.append(msg.id)
    if to_delete:
        await ctx.client.delete_messages(chat, to_delete)
    await ctx.event.reply(f"🗑 Удалено системных сообщений: {len(to_delete)}")


@command("delword", module="purger", required_right="delete_messages", description="Добавить/удалить слово в автомодерации")
async def cmd_delword(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}delword <слово|clearall>")
        return
    chat_id = (await ctx.event.get_chat()).id

    if ctx.args[0].lower() == "clearall":
        async with async_session_factory() as session:
            await session.execute(
                delete(BannedWord).where(BannedWord.account_id == ctx.account_id, BannedWord.chat_id == chat_id)
            )
            await session.commit()
        await ctx.event.reply("✅ Список запрещённых слов очищен.")
        return

    word = ctx.raw_args.lower()
    async with async_session_factory() as session:
        result = await session.execute(
            select(BannedWord).where(
                BannedWord.account_id == ctx.account_id, BannedWord.chat_id == chat_id, BannedWord.word == word
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            await session.delete(existing)
            await session.commit()
            await ctx.event.reply(f"➖ '{word}' удалено из списка.")
        else:
            session.add(BannedWord(account_id=ctx.account_id, chat_id=chat_id, word=word))
            await session.commit()
            await ctx.event.reply(f"➕ '{word}' добавлено в список.")


@command("kickall", module="purger", required_right="ban_users", description="Удалить всех, кроме админов и себя")
async def cmd_kickall(ctx: CommandContext) -> None:
    from telethon.tl.types import ChannelParticipantsAdmins

    chat = await ctx.event.get_chat()
    me = await ctx.client.get_me()
    admins = {p.id for p in await ctx.client.get_participants(chat, filter=ChannelParticipantsAdmins())}
    kicked = 0
    async for user in ctx.client.iter_participants(chat):
        if user.id in admins or user.id == me.id:
            continue
        try:
            await ctx.client.kick_participant(chat, user)
            kicked += 1
        except Exception:  # noqa: BLE001 — продолжаем удалять остальных
            continue
    await ctx.event.reply(f"✅ Удалено участников: {kicked}")
