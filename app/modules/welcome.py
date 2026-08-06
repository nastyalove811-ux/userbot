"""
Модуль Welcome — настраиваемые приветствия/прощания для новых/уходящих
участников чата. Отправка приветствия использует обычное право отправлять
сообщения (есть у всех участников), настройка команд прав не требует.
"""
from __future__ import annotations

from sqlalchemy import select

from app.db import WelcomeSettings, async_session_factory
from app.modules.base import CommandContext, command

_VARIABLES_HELP = "Переменные: {mention} {name} {username} {chat} {count} {id}"


async def _get_or_create(account_id: int, chat_id: int) -> WelcomeSettings:
    async with async_session_factory() as session:
        result = await session.execute(
            select(WelcomeSettings).where(WelcomeSettings.account_id == account_id, WelcomeSettings.chat_id == chat_id)
        )
        row = result.scalar_one_or_none()
        if row:
            return row
        row = WelcomeSettings(account_id=account_id, chat_id=chat_id)
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


@command("welcome", module="welcome", description="Управление приветствием в чате")
async def cmd_welcome(ctx: CommandContext) -> None:
    chat = await ctx.event.get_chat()

    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}welcome <on|off|test|текст>\n{_VARIABLES_HELP}")
        return

    action = ctx.args[0].lower()
    async with async_session_factory() as session:
        result = await session.execute(
            select(WelcomeSettings).where(WelcomeSettings.account_id == ctx.account_id, WelcomeSettings.chat_id == chat.id)
        )
        row = result.scalar_one_or_none()
        if not row:
            row = WelcomeSettings(account_id=ctx.account_id, chat_id=chat.id)
            session.add(row)

        if action == "on":
            row.welcome_enabled = True
            msg = "✅ Приветствие включено."
        elif action == "off":
            row.welcome_enabled = False
            msg = "✅ Приветствие выключено."
        elif action == "test":
            text = _render_template(row.welcome_text or "Добро пожаловать, {mention}!", await ctx.event.get_sender(), chat, 0)
            await ctx.event.reply(text)
            return
        else:
            reply = await ctx.event.get_reply_message()
            row.welcome_text = ctx.raw_args
            if reply and reply.media:
                row.welcome_media_file_id = str(reply.id)  # упрощённо: id сообщения-медиа в этом же чате
            msg = "✅ Текст приветствия обновлён."

        await session.commit()
    await ctx.event.reply(msg)


@command("goodbye", module="welcome", description="Управление прощанием в чате")
async def cmd_goodbye(ctx: CommandContext) -> None:
    chat = await ctx.event.get_chat()
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}goodbye <on|off|test|текст>\n{_VARIABLES_HELP}")
        return

    action = ctx.args[0].lower()
    async with async_session_factory() as session:
        result = await session.execute(
            select(WelcomeSettings).where(WelcomeSettings.account_id == ctx.account_id, WelcomeSettings.chat_id == chat.id)
        )
        row = result.scalar_one_or_none()
        if not row:
            row = WelcomeSettings(account_id=ctx.account_id, chat_id=chat.id)
            session.add(row)

        if action == "on":
            row.goodbye_enabled = True
            msg = "✅ Прощание включено."
        elif action == "off":
            row.goodbye_enabled = False
            msg = "✅ Прощание выключено."
        elif action == "test":
            text = _render_template(row.goodbye_text or "{name} покинул(а) чат.", await ctx.event.get_sender(), chat, 0)
            await ctx.event.reply(text)
            return
        else:
            row.goodbye_text = ctx.raw_args
            msg = "✅ Текст прощания обновлён."

        await session.commit()
    await ctx.event.reply(msg)


def _render_template(template: str, user, chat, count: int) -> str:
    name = getattr(user, "first_name", "") or ""
    username = f"@{user.username}" if getattr(user, "username", None) else ""
    mention = f"[{name}](tg://user?id={user.id})" if name else username
    return (
        template.replace("{mention}", mention)
        .replace("{name}", name)
        .replace("{username}", username)
        .replace("{chat}", getattr(chat, "title", ""))
        .replace("{count}", str(count))
        .replace("{id}", str(user.id))
    )


async def handle_chat_action(client, account_id: int, event) -> None:
    """
    Вызывается воркером на событие ChatAction (вход/выход участника).
    event — telethon.events.ChatAction.Event
    """
    chat = await event.get_chat()
    row = await _get_or_create(account_id, chat.id)

    if event.user_joined or event.user_added:
        if not row.welcome_enabled:
            return
        user = await event.get_user()
        participants_count = getattr(chat, "participants_count", 0)
        text = _render_template(row.welcome_text or "Добро пожаловать, {mention}!", user, chat, participants_count)
        await client.send_message(chat, text)

    elif event.user_left or event.user_kicked:
        if not row.goodbye_enabled:
            return
        user = await event.get_user()
        participants_count = getattr(chat, "participants_count", 0)
        text = _render_template(row.goodbye_text or "{name} покинул(а) чат.", user, chat, participants_count)
        await client.send_message(chat, text)
