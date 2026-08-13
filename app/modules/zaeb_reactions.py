"""
Модуль ZaebReactions — автоматические реакции на сообщения конкретных пользователей.
Поддерживает: эмодзи-реакции, автоответы текстом, включение/выключение, статистику.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from app.db import Setting, async_session_factory
from app.modules.base import CommandContext, command
from sqlalchemy import select, update, delete


# ==================== Вспомогательные функции БД ====================

async def _get_setting(account_id: int, key: str) -> Optional[str]:
    """Получить значение настройки по ключу."""
    async with async_session_factory() as session:
        stmt = select(Setting).where(
            (Setting.account_id == account_id) &
            (Setting.module == "zaeb_reactions") &
            (Setting.key == key)
        )
        result = await session.execute(stmt)
        setting = result.scalar()
        return setting.value if setting else None


async def _set_setting(account_id: int, key: str, value: str) -> None:
    """Сохранить или обновить настройку."""
    async with async_session_factory() as session:
        stmt = select(Setting).where(
            (Setting.account_id == account_id) &
            (Setting.module == "zaeb_reactions") &
            (Setting.key == key)
        )
        result = await session.execute(stmt)
        existing = result.scalar()
        if existing:
            existing.value = value
        else:
            session.add(Setting(
                account_id=account_id,
                module="zaeb_reactions",
                key=key,
                value=value
            ))
        await session.commit()


async def _del_setting(account_id: int, key: str) -> bool:
    """Удалить настройку."""
    async with async_session_factory() as session:
        stmt = select(Setting).where(
            (Setting.account_id == account_id) &
            (Setting.module == "zaeb_reactions") &
            (Setting.key == key)
        )
        result = await session.execute(stmt)
        setting = result.scalar()
        if setting:
            await session.delete(setting)
            await session.commit()
            return True
        return False


async def _get_reactions(account_id: int) -> Dict[str, Dict[str, str]]:
    """
    Получить все реакции для аккаунта.
    Возвращает: {user_id: {"emoji": "...", "message": "..."}}
    """
    async with async_session_factory() as session:
        stmt = select(Setting).where(
            (Setting.account_id == account_id) &
            (Setting.module == "zaeb_reactions") &
            (Setting.key.like("user_%"))
        )
        results = await session.execute(stmt)
        settings = results.scalars().all()

        reactions: Dict[str, Dict[str, str]] = {}
        for setting in settings:
            key = setting.key
            # ключи: user_123_emoji, user_123_message, user_123_action и т.п.
            parts = key.split("_")
            if len(parts) < 3:
                continue
            user_id = parts[1]
            suffix = "_".join(parts[2:])  # emoji, message и т.д.
            if user_id not in reactions:
                reactions[user_id] = {}
            reactions[user_id][suffix] = setting.value
        return reactions


async def _get_reaction_for_user(account_id: int, user_id: str) -> Dict[str, str]:
    """Получить реакции для конкретного пользователя."""
    return (await _get_reactions(account_id)).get(user_id, {})


async def _inc_stat(account_id: int, user_id: str) -> None:
    """Увеличить счётчик активаций для пользователя."""
    key = f"stat_{user_id}"
    async with async_session_factory() as session:
        stmt = select(Setting).where(
            (Setting.account_id == account_id) &
            (Setting.module == "zaeb_reactions") &
            (Setting.key == key)
        )
        result = await session.execute(stmt)
        setting = result.scalar()
        if setting:
            try:
                count = int(setting.value) + 1
            except ValueError:
                count = 1
            setting.value = str(count)
        else:
            session.add(Setting(
                account_id=account_id,
                module="zaeb_reactions",
                key=key,
                value="1"
            ))
        await session.commit()


async def _get_stats(account_id: int) -> Dict[str, int]:
    """Получить всю статистику активаций."""
    async with async_session_factory() as session:
        stmt = select(Setting).where(
            (Setting.account_id == account_id) &
            (Setting.module == "zaeb_reactions") &
            (Setting.key.like("stat_%"))
        )
        results = await session.execute(stmt)
        settings = results.scalars().all()
        stats = {}
        for setting in settings:
            # ключ stat_123
            user_id = setting.key.replace("stat_", "")
            try:
                stats[user_id] = int(setting.value)
            except ValueError:
                stats[user_id] = 0
        return stats


# ==================== Основная логика автореагирования ====================

# Эта функция должна быть зарегистрирована как обработчик входящих сообщений.
# Например, через декоратор @on_message или добавлением в диспетчер.
async def auto_react(event) -> None:
    """
    Обработчик новых сообщений. Автоматически реагирует, если настроено.
    """
    # Проверяем, включён ли модуль для этого аккаунта
    account_id = event.account_id  # предположим, что event содержит account_id
    enabled = await _get_setting(account_id, "module_enabled")
    if enabled != "on":
        return

    # Получаем отправителя
    sender_id = str(event.sender_id)  # или event.from_user.id
    reactions = await _get_reaction_for_user(account_id, sender_id)
    if not reactions:
        return

    # Выполняем реакции
    if "emoji" in reactions:
        emoji = reactions["emoji"]
        try:
            # предполагаем, что у event есть метод react()
            await event.react(emoji)
        except Exception as e:
            # логируем ошибку
            pass

    if "message" in reactions:
        msg = reactions["message"]
        try:
            await event.reply(msg)
        except Exception:
            pass

    # Увеличиваем статистику
    await _inc_stat(account_id, sender_id)


# ==================== Команды ====================

@command(
    "zaebr",
    module="zaeb_reactions",
    description="Управление автореакциями: on/off/status/list/clear",
    admin_only=False,
)
async def cmd_zaebr(ctx: CommandContext) -> None:
    """Главная команда управления."""
    if not ctx.args:
        # Показать статус
        enabled = await _get_setting(ctx.account_id, "module_enabled") == "on"
        reactions = await _get_reactions(ctx.account_id)
        stats = await _get_stats(ctx.account_id)
        total_activations = sum(stats.values())
        reply = (
            f"🎭 **ZaebReactions**\n"
            f"Статус: {'✅ Включён' if enabled else '❌ Выключен'}\n"
            f"Пользователей с реакциями: {len(reactions)}\n"
            f"Всего активаций: {total_activations}\n\n"
            f"Команды:\n"
            f"  {ctx.prefix}zaebr on/off — включить/выключить\n"
            f"  {ctx.prefix}zaebr list — список реакций\n"
            f"  {ctx.prefix}zaebr clear — удалить все реакции\n"
            f"  {ctx.prefix}zaebr stats — статистика по пользователям"
        )
        await ctx.event.reply(reply)
        return

    action = ctx.args[0].lower()

    if action == "on":
        await _set_setting(ctx.account_id, "module_enabled", "on")
        await ctx.event.reply("✅ Автореакции включены.")
    elif action == "off":
        await _set_setting(ctx.account_id, "module_enabled", "off")
        await ctx.event.reply("❌ Автореакции отключены.")
    elif action == "list":
        reactions = await _get_reactions(ctx.account_id)
        if not reactions:
            await ctx.event.reply("📋 Список реакций пуст.")
            return
        lines = []
        for uid, r in reactions.items():
            parts = []
            if "emoji" in r:
                parts.append(f"эмодзи {r['emoji']}")
            if "message" in r:
                parts.append(f"сообщение \"{r['message'][:30]}...\"")
            lines.append(f"• {uid}: {', '.join(parts)}")
        await ctx.event.reply("📋 **Реакции:**\n" + "\n".join(lines))
    elif action == "clear":
        # Удаляем все реакции (ключи user_*)
        async with async_session_factory() as session:
            stmt = delete(Setting).where(
                (Setting.account_id == ctx.account_id) &
                (Setting.module == "zaeb_reactions") &
                (Setting.key.like("user_%"))
            )
            await session.execute(stmt)
            await session.commit()
        await ctx.event.reply("🧹 Все автореакции удалены.")
    elif action == "stats":
        stats = await _get_stats(ctx.account_id)
        if not stats:
            await ctx.event.reply("📊 Статистика пуста.")
            return
        lines = [f"• {uid}: {count} активаций" for uid, count in sorted(stats.items(), key=lambda x: -x[1])]
        await ctx.event.reply("📊 **Статистика активаций:**\n" + "\n".join(lines[:20]))
    else:
        await ctx.event.reply(
            f"Неизвестная подкоманда.\n"
            f"Использование: {ctx.prefix}zaebr <on|off|list|clear|stats>"
        )


@command(
    "addzaebr",
    module="zaeb_reactions",
    description="Добавить реакцию пользователю (эмодзи или сообщение)",
    admin_only=False,
)
async def cmd_addzaebr(ctx: CommandContext) -> None:
    """
    Формат: addzaebr <user> <emoji|message> <значение>
    """
    if len(ctx.args) < 3:
        await ctx.event.reply(
            f"Использование: {ctx.prefix}addzaebr <username|user_id> <emoji|message> <значение>"
        )
        return

    user_target = ctx.args[0]
    rtype = ctx.args[1].lower()
    value = " ".join(ctx.args[2:])

    if rtype not in ("emoji", "message"):
        await ctx.event.reply("Тип должен быть 'emoji' или 'message'.")
        return

    # Проверка, что эмодзи — один символ (примерно)
    if rtype == "emoji":
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # эмоции
            "\U0001F300-\U0001F5FF"  # символы и пиктограммы
            "\U0001F680-\U0001F6FF"  # транспорт и карты
            "\U0001F700-\U0001F77F"  # алхимические символы
            "\U0001F780-\U0001F7FF"  # геометрические формы
            "\U0001F800-\U0001F8FF"  # дополнительные стрелки
            "\U0001F900-\U0001F9FF"  # дополнительные символы
            "\U0001FA00-\U0001FA6F"  # дополнительные пиктограммы
            "\U0001FA70-\U0001FAFF"  # дополнительные символы
            "\U00002702-\U000027B0"  # прочее
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )
        if not emoji_pattern.fullmatch(value.strip()):
            await ctx.event.reply("❌ Указанный эмодзи не распознан. Попробуйте другой.")
            return

    # Сохраняем
    key = f"user_{user_target}_{rtype}"
    await _set_setting(ctx.account_id, key, value)
    await ctx.event.reply(
        f"✅ Добавлена {rtype}-реакция для {user_target}:\n"
        f"📌 {value}"
    )


@command(
    "delzaebr",
    module="zaeb_reactions",
    description="Удалить конкретную реакцию пользователя",
    admin_only=False,
)
async def cmd_delzaebr(ctx: CommandContext) -> None:
    """Удалить реакцию определённого типа."""
    if len(ctx.args) < 2:
        await ctx.event.reply(
            f"Использование: {ctx.prefix}delzaebr <user> <emoji|message|all>"
        )
        return

    user_target = ctx.args[0]
    rtype = ctx.args[1].lower()

    if rtype == "all":
        # удаляем все ключи user_{user_target}_*
        async with async_session_factory() as session:
            stmt = delete(Setting).where(
                (Setting.account_id == ctx.account_id) &
                (Setting.module == "zaeb_reactions") &
                (Setting.key.startswith(f"user_{user_target}_"))
            )
            await session.execute(stmt)
            await session.commit()
        await ctx.event.reply(f"🧹 Все реакции для {user_target} удалены.")
    elif rtype in ("emoji", "message"):
        key = f"user_{user_target}_{rtype}"
        if await _del_setting(ctx.account_id, key):
            await ctx.event.reply(f"✅ {rtype}-реакция для {user_target} удалена.")
        else:
            await ctx.event.reply(f"❌ {rtype}-реакция для {user_target} не найдена.")
    else:
        await ctx.event.reply("Тип должен быть 'emoji', 'message' или 'all'.")


@command(
    "zaebr_emoji",
    module="zaeb_reactions",
    description="Быстро установить эмодзи-реакцию (устаревшая, используйте addzaebr)",
    admin_only=False,
)
async def cmd_zaebr_emoji(ctx: CommandContext) -> None:
    """Установить эмодзи для пользователя (сохраняется отдельно)."""
    if len(ctx.args) < 2:
        await ctx.event.reply(f"Использование: {ctx.prefix}zaebr_emoji <user> <emoji>")
        return
    user_target = ctx.args[0]
    emoji = ctx.args[1]
    key = f"user_{user_target}_emoji"
    await _set_setting(ctx.account_id, key, emoji)
    await ctx.event.reply(f"✅ Эмодзи для {user_target} установлен: {emoji}")


@command(
    "zaebr_message",
    module="zaeb_reactions",
    description="Быстро установить автоответ (устаревшая, используйте addzaebr)",
    admin_only=False,
)
async def cmd_zaebr_message(ctx: CommandContext) -> None:
    """Установить автоответ для пользователя."""
    if len(ctx.args) < 2:
        await ctx.event.reply(f"Использование: {ctx.prefix}zaebr_message <user> <сообщение>")
        return
    user_target = ctx.args[0]
    message = " ".join(ctx.args[1:])
    key = f"user_{user_target}_message"
    await _set_setting(ctx.account_id, key, message)
    await ctx.event.reply(f"✅ Автоответ для {user_target} установлен:\n💬 \"{message}\"")


@command(
    "zaebr_reaction",
    module="zaeb_reactions",
    description="Отправить быструю реакцию (эмодзи) в ответ",
    admin_only=False,
)
async def cmd_zaebr_reaction(ctx: CommandContext) -> None:
    """Быстро поставить эмодзи (не авто, а ручная команда)."""
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}zaebr_reaction <emoji> [количество]")
        return
    emoji = ctx.args[0]
    count = 1
    if len(ctx.args) > 1:
        try:
            count = min(int(ctx.args[1]), 5)
        except ValueError:
            pass
    await ctx.event.reply(emoji * count)


@command(
    "zaebr_stats",
    module="zaeb_reactions",
    description="Показать статистику активаций",
    admin_only=False,
)
async def cmd_zaebr_stats(ctx: CommandContext) -> None:
    """Показать статистику."""
    stats = await _get_stats(ctx.account_id)
    if not stats:
        await ctx.event.reply("📊 Статистика пуста.")
        return
    lines = [f"• {uid}: {count} активаций" for uid, count in sorted(stats.items(), key=lambda x: -x[1])]
    await ctx.event.reply("📊 **Статистика активаций:**\n" + "\n".join(lines[:20]))


@command(
    "zaebr_resetstats",
    module="zaeb_reactions",
    description="Сбросить всю статистику",
    admin_only=False,
)
async def cmd_zaebr_resetstats(ctx: CommandContext) -> None:
    """Сбросить статистику."""
    async with async_session_factory() as session:
        stmt = delete(Setting).where(
            (Setting.account_id == ctx.account_id) &
            (Setting.module == "zaeb_reactions") &
            (Setting.key.like("stat_%"))
        )
        await session.execute(stmt)
        await session.commit()
    await ctx.event.reply("🧹 Статистика сброшена.")
