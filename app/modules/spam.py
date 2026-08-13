"""
Модуль спама — массовая рассылка сообщений с различными форматами.
Поддерживает: обычный спам, циклический спам, форматированный спам (Markdown),
отложенный спам, защита от случайного массового спама, логирование.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.modules.base import CommandContext, command

logger = logging.getLogger(__name__)

# Максимальное количество сообщений для подтверждения
MAX_SPAM_CONFIRM = 10
# Задержка между сообщениями при циклическом спаме (сек)
CSPAM_INTERVAL = 0.5
# Максимальный размер текста для форматированного спама
MAX_FORMAT_LENGTH = 4096


@command(
    "spam",
    module="spam",
    description="Отправить N одинаковых сообщений",
    admin_only=False,
)
async def cmd_spam(ctx: CommandContext) -> None:
    """
    Использование: spam <количество> <текст>
    Отправляет указанное количество копий текста.
    При количестве > MAX_SPAM_CONFIRM выводится предупреждение.
    """
    if len(ctx.args) < 2:
        await ctx.event.reply(
            f"❌ Использование: {ctx.prefix}spam <количество> <текст>"
        )
        return

    try:
        count = int(ctx.args[0])
    except ValueError:
        await ctx.event.reply("❌ Количество должно быть числом.")
        return

    if count < 1:
        await ctx.event.reply("❌ Количество должно быть больше 0.")
        return

    text = " ".join(ctx.args[1:])
    if not text:
        await ctx.event.reply("❌ Текст не может быть пустым.")
        return

    # Предупреждение при большом количестве
    if count > MAX_SPAM_CONFIRM:
        await ctx.event.reply(
            f"⚠️ Вы собираетесь отправить **{count}** сообщений. "
            f"Это может вызвать флуд. Продолжаем..."
        )

    # Отправка спама
    for i in range(count):
        try:
            await ctx.event.reply(text)
            await asyncio.sleep(0.1)  # небольшая задержка
        except Exception as e:
            logger.error(f"Ошибка при спаме: {e}")
            await ctx.event.reply(f"❌ Ошибка на сообщении {i+1}: {e}")
            return

    logger.info(f"Спам {count} сообщений от {ctx.event.sender_id} в чате {ctx.event.chat_id}")
    await ctx.event.reply(f"✅ Отправлено {count} сообщений.")


@command(
    "cspam",
    module="spam",
    description="Циклический спам (отправляет текст с задержкой)",
    admin_only=False,
)
async def cmd_cspam(ctx: CommandContext) -> None:
    """
    Использование: cspam <количество> <текст>
    Отправляет текст каждые CSPAM_INTERVAL секунд, всего count раз.
    """
    if len(ctx.args) < 2:
        await ctx.event.reply(
            f"❌ Использование: {ctx.prefix}cspam <количество> <текст>"
        )
        return

    try:
        count = int(ctx.args[0])
    except ValueError:
        await ctx.event.reply("❌ Количество должно быть числом.")
        return

    if count < 1:
        await ctx.event.reply("❌ Количество должно быть больше 0.")
        return

    text = " ".join(ctx.args[1:])
    if not text:
        await ctx.event.reply("❌ Текст не может быть пустым.")
        return

    if count > MAX_SPAM_CONFIRM:
        await ctx.event.reply(
            f"⚠️ Вы собираетесь отправить **{count}** сообщений с задержкой. Продолжаем..."
        )

    for i in range(count):
        try:
            await ctx.event.reply(text)
            if i < count - 1:
                await asyncio.sleep(CSPAM_INTERVAL)
        except Exception as e:
            logger.error(f"Ошибка при циклическом спаме: {e}")
            await ctx.event.reply(f"❌ Ошибка на сообщении {i+1}: {e}")
            return

    logger.info(f"Циклический спам {count} сообщений от {ctx.event.sender_id}")
    await ctx.event.reply(f"✅ Отправлено {count} сообщений с задержкой.")


@command(
    "formatspam",
    module="spam",
    description="Форматированный спам с поддержкой Markdown (жирный, курсив, код и т.д.)",
    admin_only=False,
)
# Псевдоним "wspam" убран, так как декоратор не поддерживает aliases.
# При желании можно создать отдельную команду-ссылку, но это необязательно.
async def cmd_formatspam(ctx: CommandContext) -> None:
    """
    Использование: formatspam <количество> <текст с Markdown>
    Поддерживает: **жирный**, *курсив*, `код`, ||спойлер||, [ссылка](url)
    """
    if len(ctx.args) < 2:
        await ctx.event.reply(
            f"❌ Использование: {ctx.prefix}formatspam <количество> <текст>"
        )
        return

    try:
        count = int(ctx.args[0])
    except ValueError:
        await ctx.event.reply("❌ Количество должно быть числом.")
        return

    if count < 1:
        await ctx.event.reply("❌ Количество должно быть больше 0.")
        return

    text = " ".join(ctx.args[1:])
    if len(text) > MAX_FORMAT_LENGTH:
        await ctx.event.reply(f"❌ Текст слишком длинный (макс. {MAX_FORMAT_LENGTH} символов).")
        return

    if count > MAX_SPAM_CONFIRM:
        await ctx.event.reply(
            f"⚠️ Отправить {count} форматированных сообщений? Продолжаем..."
        )

    for i in range(count):
        try:
            await ctx.event.reply(text, parse_mode="Markdown")
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Ошибка при форматированном спаме: {e}")
            await ctx.event.reply(f"❌ Ошибка: {e}")
            return

    logger.info(f"Форматированный спам {count} сообщений от {ctx.event.sender_id}")
    await ctx.event.reply(f"✅ Отправлено {count} форматированных сообщений.")


@command(
    "delayspam",
    module="spam",
    description="Отложенный спам (отправить через указанное время)",
    admin_only=False,
)
async def cmd_delayspam(ctx: CommandContext) -> None:
    """
    Использование: delayspam <время_в_секундах> <количество> <текст>
    Отправляет спам после указанной задержки.
    """
    if len(ctx.args) < 3:
        await ctx.event.reply(
            f"❌ Использование: {ctx.prefix}delayspam <секунды> <количество> <текст>"
        )
        return

    try:
        delay = int(ctx.args[0])
    except ValueError:
        await ctx.event.reply("❌ Время задержки должно быть числом (сек).")
        return

    if delay < 1:
        await ctx.event.reply("❌ Задержка должна быть больше 0.")
        return

    try:
        count = int(ctx.args[1])
    except ValueError:
        await ctx.event.reply("❌ Количество должно быть числом.")
        return

    if count < 1:
        await ctx.event.reply("❌ Количество должно быть больше 0.")
        return

    text = " ".join(ctx.args[2:])
    if not text:
        await ctx.event.reply("❌ Текст не может быть пустым.")
        return

    # Подтверждение не требуется, просто информируем
    await ctx.event.reply(
        f"⏳ Отложенный спам будет отправлен через **{delay}** секунд.\n"
        f"Количество: {count}\nТекст: {text[:50]}...\n"
        f"Для отмены напишите `cancel` в течение {delay} секунд (не реализовано)."
    )

    # Запускаем фоновую задачу
    async def delayed_task():
        await asyncio.sleep(delay)
        for i in range(count):
            try:
                await ctx.event.reply(text)
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Ошибка при отложенном спаме: {e}")
                await ctx.event.reply(f"❌ Ошибка: {e}")
                return
        logger.info(f"Отложенный спам {count} сообщений от {ctx.event.sender_id}")
        await ctx.event.reply(f"✅ Отложенный спам ({count} сообщений) отправлен.")

    asyncio.create_task(delayed_task())
    # Команда завершается, задача продолжает работать
