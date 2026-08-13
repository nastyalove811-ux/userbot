"""
Модуль tagall — массовое упоминание участников чата.
Поддерживает: tagall (всех участников), tagrole (по роли: admin, member, owner),
исключение самого бота, защита от флуда, обработка ошибок.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from app.modules.base import CommandContext, command

logger = logging.getLogger(__name__)

# Количество упоминаний в одном сообщении (Telegram лимит ~50, но ставим 100 для безопасности)
CHUNK_SIZE = 50
# Задержка между отправками чанков (сек)
DELAY_BETWEEN_CHUNKS = 1


@command(
    "tagall",
    module="tagall",
    description="Упомянуть всех участников чата (с разбивкой по чанкам)",
    admin_only=False,
)
async def cmd_tagall(ctx: CommandContext) -> None:
    """
    Использование: tagall [текст_причины]
    Упоминает всех участников группы, исключая бота.
    """
    reason = " ".join(ctx.args) if ctx.args else "внимание"

    # Получаем список участников (предполагаем, что ctx.event.get_chat_members() существует)
    try:
        members = await ctx.event.get_chat_members()
    except AttributeError:
        await ctx.event.reply("❌ Этот метод не поддерживается в данном клиенте.")
        return
    except Exception as e:
        logger.error(f"Ошибка получения участников: {e}")
        await ctx.event.reply(f"❌ Не удалось получить список участников: {e}")
        return

    # Исключаем бота (своего аккаунта)
    bot_id = ctx.bot_id  # предполагаем, что у ctx есть bot_id
    members = [m for m in members if m.user.id != bot_id]

    if not members:
        await ctx.event.reply("❌ Нет участников для упоминания (или все — боты).")
        return

    total = len(members)
    await ctx.event.reply(f"👥 Начинаем упоминание **{total}** участников (причина: {reason})")

    # Разбиваем на чанки
    for i in range(0, total, CHUNK_SIZE):
        chunk = members[i:i+CHUNK_SIZE]
        # Формируем текст: упоминания через запятую
        mentions = []
        for member in chunk:
            # Используем специальный формат для упоминания: [name](tg://user?id=id)
            # или просто @username, если есть
            user = member.user
            if user.username:
                mentions.append(f"@{user.username}")
            else:
                mentions.append(f"[{user.first_name}](tg://user?id={user.id})")
        text = f"Уважаемые {', '.join(mentions)}!\nПричина: {reason}"
        try:
            await ctx.event.reply(text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Ошибка отправки чанка: {e}")
            await ctx.event.reply(f"❌ Ошибка при отправке: {e}")
            return
        # Задержка между чанками
        if i + CHUNK_SIZE < total:
            await asyncio.sleep(DELAY_BETWEEN_CHUNKS)

    logger.info(f"Tagall выполнен для чата {ctx.event.chat_id} ({total} участников)")
    await ctx.event.reply(f"✅ Все {total} участников упомянуты.")


@command(
    "tagrole",
    module="tagall",
    description="Упомянуть участников с определённой ролью (admin, member, owner)",
    admin_only=False,
)
async def cmd_tagrole(ctx: CommandContext) -> None:
    """
    Использование: tagrole <роль> [текст_причины]
    Роли: admin, member, owner.
    """
    if not ctx.args:
        await ctx.event.reply(
            f"❌ Использование: {ctx.prefix}tagrole <admin|member|owner> [причина]"
        )
        return

    role = ctx.args[0].lower()
    reason = " ".join(ctx.args[1:]) if len(ctx.args) > 1 else "внимание"

    # Проверка роли
    if role not in ("admin", "member", "owner"):
        await ctx.event.reply("❌ Роль должна быть: admin, member или owner.")
        return

    try:
        members = await ctx.event.get_chat_members()
    except Exception as e:
        logger.error(f"Ошибка получения участников: {e}")
        await ctx.event.reply(f"❌ Не удалось получить список участников: {e}")
        return

    bot_id = ctx.bot_id
    # Фильтрация по роли
    filtered = []
    for m in members:
        if m.user.id == bot_id:
            continue
        if role == "owner" and m.status == "creator":
            filtered.append(m)
        elif role == "admin" and m.status in ("creator", "administrator"):
            filtered.append(m)
        elif role == "member" and m.status == "member":
            filtered.append(m)

    if not filtered:
        await ctx.event.reply(f"❌ Нет участников с ролью '{role}' (или все — боты).")
        return

    total = len(filtered)
    await ctx.event.reply(f"👥 Начинаем упоминание **{total}** участников с ролью '{role}' (причина: {reason})")

    for i in range(0, total, CHUNK_SIZE):
        chunk = filtered[i:i+CHUNK_SIZE]
        mentions = []
        for member in chunk:
            user = member.user
            if user.username:
                mentions.append(f"@{user.username}")
            else:
                mentions.append(f"[{user.first_name}](tg://user?id={user.id})")
        text = f"Уважаемые {', '.join(mentions)} (роль: {role})!\nПричина: {reason}"
        try:
            await ctx.event.reply(text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Ошибка отправки чанка: {e}")
            await ctx.event.reply(f"❌ Ошибка: {e}")
            return
        if i + CHUNK_SIZE < total:
            await asyncio.sleep(DELAY_BETWEEN_CHUNKS)

    logger.info(f"Tagrole {role} выполнен для чата {ctx.event.chat_id} ({total} участников)")
    await ctx.event.reply(f"✅ Все {total} участников с ролью '{role}' упомянуты.")


# Если есть команда mention для одиночного упоминания, можно добавить, но она не обязательна.
