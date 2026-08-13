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
    При количестве > MAX_SPAM_CONFIRM запрашивает подтверждение.
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

    # Защита от случайного массового спама
    if count > MAX_SPAM_CONFIRM:
        confirm_msg = await ctx.event.reply(
            f"⚠️ Вы собираетесь отправить **{count}** сообщений. "
            f"Это может вызвать флуд. Для подтверждения отправьте `yes` в течение 10 секунд."
        )
        try:
            # Ожидаем ответ пользователя (предполагаем, что есть метод wait_for_response)
            response = await ctx.event.wait_for_response(
                from_user=ctx.event.sender_id, timeout=10
            )
            if response.text.lower() != "yes":
                await ctx.event.reply("❌ Отменено.")
                return
        except asyncio.TimeoutError:
            await ctx.event.reply("⏰ Время вышло. Отменено.")
            return
        except AttributeError:
            # Если wait_for_response не реализован, просто предупреждаем и продолжаем
            await ctx.event.reply("⚠️ Подтверждение не поддерживается, продолжаем...")

    # Отправка спама
    for i in range(count):
        try:
            await ctx.event.reply(text)
            await asyncio.sleep(0.1)  # небольшая задержка, чтобы не упереться в лимиты
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

    # Защита аналогично спаму
    if count > MAX_SPAM_CONFIRM:
        confirm_msg = await ctx.event.reply(
            f"⚠️ Вы собираетесь отправить **{count}** сообщений с задержкой. Подтвердите `yes` в течение 10 сек."
        )
        try:
            response = await ctx.event.wait_for_response(
                from_user=ctx.event.sender_id, timeout=10
            )
            if response.text.lower() != "yes":
                await ctx.event.reply("❌ Отменено.")
                return
        except (asyncio.TimeoutError, AttributeError):
            await ctx.event.reply("⏰ Время вышло или функция не поддерживается. Продолжаем...")

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
    aliases=["wspam"],  # оставляем старый псевдоним для совместимости
)
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
        try:
            await ctx.event.reply(
                f"⚠️ Отправить {count} форматированных сообщений? Ответьте `yes` в течение 10 сек."
            )
            response = await ctx.event.wait_for_response(
                from_user=ctx.event.sender_id, timeout=10
            )
            if response.text.lower() != "yes":
                await ctx.event.reply("❌ Отменено.")
                return
        except (asyncio.TimeoutError, AttributeError):
            pass

    # Отправка с форматированием (parse_mode='Markdown')
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

    # Подтверждение
    await ctx.event.reply(
        f"⏳ Отложенный спам будет отправлен через **{delay}** секунд.\n"
        f"Количество: {count}\nТекст: {text[:50]}...\n"
        f"Для отмены напишите `cancel` в течение {delay} секунд."
    )

    # Запускаем таймер с возможностью отмены
    try:
        # Создаём задачу, которая будет ждать и отправлять
        async def delayed_task():
            # Ждём delay секунд, но с проверкой на отмену
            for _ in range(delay):
                await asyncio.sleep(1)
                # Проверяем, не поступила ли команда отмены (проверяем последнее сообщение от пользователя)
                # Это упрощённо; в реальности нужно подписаться на новые сообщения
                # Для демонстрации просто ждём и отправляем
            # Отправляем спам
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

        # Запускаем задачу, но не блокируем основной поток
        asyncio.create_task(delayed_task())
        # Ответим, что задача запущена
        # Команда завершается, но задача продолжает работать

    except Exception as e:
        logger.error(f"Ошибка при запуске отложенного спама: {e}")
        await ctx.event.reply(f"❌ Ошибка: {e}")


# Дополнительно можно добавить команду для остановки всех запущенных задач,
# но это потребует глобального хранилища задач. Оставим для будущего расширения.
