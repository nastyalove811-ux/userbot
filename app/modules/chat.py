"""
Модуль Chat — просмотр информации о чатах/пользователях, отправка сообщений.
Ни одна команда этого модуля не требует прав администратора в чате: они либо
только читают данные, либо доступны любому участнику (invite/kickme/send).
"""
from __future__ import annotations

from telethon.tl.types import Channel, Chat, User

from app.modules.base import CommandContext, command


def _display_name(entity) -> str:
    if isinstance(entity, User):
        return " ".join(filter(None, [entity.first_name, entity.last_name])) or f"id{entity.id}"
    return getattr(entity, "title", str(getattr(entity, "id", "")))


@command("id", module="chat", description="ID пользователя или текущего чата")
async def cmd_id(ctx: CommandContext) -> None:
    reply = await ctx.event.get_reply_message()
    if reply:
        await ctx.event.reply(f"🆔 ID отправителя: {reply.sender_id}")
        return
    if ctx.args:
        entity = await ctx.client.get_entity(ctx.args[0])
        await ctx.event.reply(f"🆔 ID {_display_name(entity)}: {entity.id}")
        return
    chat = await ctx.event.get_chat()
    await ctx.event.reply(f"🆔 ID текущего чата: {chat.id}")


@command("invite", module="chat", description="Пригласить пользователя в текущий чат")
async def cmd_invite(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}invite <кто>")
        return
    chat = await ctx.event.get_chat()
    user = await ctx.client.get_entity(ctx.args[0])
    await ctx.client.edit_permissions(chat, user)  # добавление через InviteToChannelRequest ниже
    from telethon.tl.functions.channels import InviteToChannelRequest
    from telethon.tl.functions.messages import AddChatUserRequest

    try:
        if isinstance(chat, Channel):
            await ctx.client(InviteToChannelRequest(chat, [user]))
        else:
            await ctx.client(AddChatUserRequest(chat.id, user, fwd_limit=50))
        await ctx.event.reply(f"✅ {_display_name(user)} приглашён(а) в чат.")
    except Exception as exc:  # noqa: BLE001 — показываем причину пользователю
        await ctx.event.reply(f"❌ Не удалось пригласить: {exc}")


@command("kickme", module="chat", description="Покинуть текущий чат")
async def cmd_kickme(ctx: CommandContext) -> None:
    reason = ctx.raw_args or None
    chat = await ctx.event.get_chat()
    await ctx.client.delete_dialog(chat)
    # событие уже недоступно для ответа после выхода — reason просто логируется воркером


@command("members", module="chat", description="Список участников чата с поиском по имени")
async def cmd_members(ctx: CommandContext) -> None:
    chat = await ctx.event.get_chat()
    search = ctx.raw_args or None
    participants = await ctx.client.get_participants(chat, search=search, limit=200)
    if not participants:
        await ctx.event.reply("Участники не найдены.")
        return
    lines = [f"👥 Участники ({len(participants)}{'​, фильтр: ' + search if search else ''}):"]
    for user in participants[:50]:
        lines.append(f"• {_display_name(user)} (id{user.id})")
    if len(participants) > 50:
        lines.append(f"... и ещё {len(participants) - 50}")
    await ctx.event.reply("\n".join(lines))


@command("admins", module="chat", description="Список администраторов чата")
async def cmd_admins(ctx: CommandContext) -> None:
    from telethon.tl.types import ChannelParticipantsAdmins

    chat = await ctx.event.get_chat()
    admins = await ctx.client.get_participants(chat, filter=ChannelParticipantsAdmins())
    if not admins:
        await ctx.event.reply("Администраторы не найдены (или это не супергруппа/канал).")
        return
    lines = ["👮 Администраторы:"]
    for user in admins:
        rank = getattr(getattr(user, "participant", None), "rank", None)
        lines.append(f"• {_display_name(user)}" + (f" ({rank})" if rank else ""))
    await ctx.event.reply("\n".join(lines))


@command("bots", module="chat", description="Список ботов в чате")
async def cmd_bots(ctx: CommandContext) -> None:
    chat = await ctx.event.get_chat()
    participants = await ctx.client.get_participants(chat, limit=500)
    bots = [p for p in participants if getattr(p, "bot", False)]
    if not bots:
        await ctx.event.reply("Ботов в чате не найдено.")
        return
    lines = ["🤖 Боты:"] + [f"• {_display_name(b)} (@{b.username})" for b in bots]
    await ctx.event.reply("\n".join(lines))


@command("link", module="chat", description="Получить ссылку-приглашение")
async def cmd_link(ctx: CommandContext) -> None:
    chat = await ctx.event.get_chat()
    try:
        invite = await ctx.client(__import__(
            "telethon.tl.functions.messages", fromlist=["ExportChatInviteRequest"]
        ).ExportChatInviteRequest(chat))
        await ctx.event.reply(f"🔗 {invite.link}")
    except Exception as exc:  # noqa: BLE001
        await ctx.event.reply(f"❌ Не удалось получить ссылку: {exc}")


@command("common", module="chat", description="Общие чаты с пользователем")
async def cmd_common(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}common <кто>")
        return
    from telethon.tl.functions.messages import GetCommonChatsRequest

    user = await ctx.client.get_entity(ctx.args[0])
    result = await ctx.client(GetCommonChatsRequest(user_id=user, max_id=0, limit=100))
    if not result.chats:
        await ctx.event.reply("Общих чатов не найдено.")
        return
    lines = ["🔗 Общие чаты:"] + [f"• {c.title}" for c in result.chats]
    await ctx.event.reply("\n".join(lines))


@command("chats", module="chat", description="Список всех диалогов с превью")
async def cmd_chats(ctx: CommandContext) -> None:
    dialogs = await ctx.client.get_dialogs(limit=30)
    lines = ["💬 Диалоги:"]
    for d in dialogs:
        preview = (d.message.message[:40] + "…") if d.message and d.message.message else ""
        lines.append(f"• {d.name} — {preview}")
    await ctx.event.reply("\n".join(lines))


@command("chat", module="chat", description="История сообщений указанного чата")
async def cmd_chat(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}chat <id/username>")
        return
    entity = await ctx.client.get_entity(ctx.args[0])
    messages = await ctx.client.get_messages(entity, limit=20)
    lines = [f"📜 Последние сообщения в {_display_name(entity)}:"]
    for m in reversed(messages):
        text = (m.message or "[медиа]")[:80]
        lines.append(f"[{m.date:%d.%m %H:%M}] {text}")
    await ctx.event.reply("\n".join(lines))


@command("send", module="chat", description="Отправить сообщение в указанный чат")
async def cmd_send(ctx: CommandContext) -> None:
    if len(ctx.args) < 2:
        await ctx.event.reply(f"Использование: {ctx.prefix}send <чат> <текст>")
        return
    target, text = ctx.args[0], " ".join(ctx.args[1:])
    entity = await ctx.client.get_entity(target)
    await ctx.client.send_message(entity, text)
    await ctx.event.reply(f"✅ Отправлено в {_display_name(entity)}")


@command("reply", module="chat", description="Ответить на конкретное сообщение")
async def cmd_reply(ctx: CommandContext) -> None:
    reply = await ctx.event.get_reply_message()
    if not reply or not ctx.args:
        await ctx.event.reply(f"Использование: ответом на сообщение — {ctx.prefix}reply <текст>")
        return
    await reply.reply(ctx.raw_args)
