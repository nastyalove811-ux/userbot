"""
Модуль ZaebReactions — автоматические реакции на сообщения конкретных пользователей.
Поддерживает: эмодзи-реакции, автоответы текстом, действия (pin, delete, ban),
фильтры по чатам, временные реакции (автоудаление), включение/выключение,
статистику, экспорт/импорт настроек.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Union

from app.db import Setting, async_session_factory
from app.modules.base import CommandContext, command
from sqlalchemy import select, delete, update

logger = logging.getLogger(__name__)


# ---------------------- Вспомогательные функции БД ----------------------

async def _get_setting(account_id: int, key: str) -> Optional[str]:
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
    async with async_session_factory() as session:
        stmt = delete(Setting).where(
            (Setting.account_id == account_id) &
            (Setting.module == "zaeb_reactions") &
            (Setting.key == key)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


async def _get_reactions(account_id: int) -> Dict[str, Dict[str, str]]:
    """
    Возвращает: {user_id: {"emoji": "...", "message": "...", "action": "...", ...}}
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
            key = setting.key  # user_123_emoji, user_123_message, user_123_action, user_123_chats, user_123_ttl
            parts = key.split("_")
            if len(parts) < 3:
                continue
            user_id = parts[1]
            suffix = "_".join(parts[2:])  # emoji, message, action, chats, ttl
            if user_id not in reactions:
                reactions[user_id] = {}
            reactions[user_id][suffix] = setting.value
        return reactions


async def _get_reaction_for_user(account_id: int, user_id: str) -> Dict[str, str]:
    return (await _get_reactions(account_id)).get(user_id, {})


async def _set_reaction_field(account_id: int, user_id: str, field: str, value: str) -> None:
    key = f"user_{user_id}_{field}"
    await _set_setting(account_id, key, value)


async def _del_reaction_field(account_id: int, user_id: str, field: str) -> bool:
    key = f"user_{user_id}_{field}"
    return await _del_setting(account_id, key)


async def _inc_stat(account_id: int, user_id: str) -> None:
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
            user_id = setting.key.replace("stat_", "")
            try:
                stats[user_id] = int(setting.value)
            except ValueError:
                stats[user_id] = 0
        return stats


# ---------------------- Основной обработчик ----------------------

async def zaebr_auto_react(event) -> None:
    """
    Обработчик новых сообщений. Должен быть зарегистрирован в основном цикле.
    """
    account_id = event.account_id
    # Проверка включения
    enabled = await _get_setting(account_id, "module_enabled")
    if enabled != "on":
        return

    sender_id = str(event.sender_id)
    reactions = await _get_reaction_for_user(account_id, sender_id)
    if not reactions:
        return

    # Проверка фильтра по чатам (если задан)
    if "chats" in reactions:
        allowed_chats = [c.strip() for c in reactions["chats"].split(",") if c.strip()]
        if allowed_chats and str(event.chat_id) not in allowed_chats:
            return

    # Выполняем реакции
    if "emoji" in reactions:
        try:
            await event.react(reactions["emoji"])
        except Exception as e:
            logger.error(f"Ошибка реакции эмодзи: {e}")

    if "message" in reactions:
        try:
            await event.reply(reactions["message"])
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")

    if "action" in reactions:
        action = reactions["action"]
        try:
            if action == "pin":
                await event.pin()
            elif action == "delete":
                await event.delete()
            elif action == "ban":
                # Предполагаем, что есть метод ban_user
                await event.ban_user(sender_id)
            elif action == "kick":
                await event.kick_user(sender_id)
            # другие действия можно добавить
        except Exception as e:
            logger.error(f"Ошибка выполнения действия {action}: {e}")

    # Увеличиваем статистику
    await _inc_stat(account_id, sender_id)

    # Если задан TTL (время жизни реакции), запускаем задачу на удаление через N минут
    if "ttl" in reactions:
        try:
            ttl_minutes = int(reactions["ttl"])
            if ttl_minutes > 0:
                async def remove_reaction():
                    await asyncio.sleep(ttl_minutes * 60)
                    # Удаляем все поля для этого пользователя
                    for field in ("emoji", "message", "action", "chats", "ttl"):
                        await _del_reaction_field(account_id, sender_id, field)
                    logger.info(f"Автоудалены реакции для {sender_id} по TTL")
                asyncio.create_task(remove_reaction())
        except ValueError:
            pass


# ---------------------- Команды управления ----------------------

@command(
    "zaebr",
    module="zaeb_reactions",
    description="Управление автореакциями: on/off/status/list/clear/stats/export/import",
    admin_only=False,
)
async def cmd_zaebr(ctx: CommandContext) -> None:
    if not ctx.args:
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
            f"  {ctx.prefix}zaebr stats — статистика по пользователям\n"
            f"  {ctx.prefix}zaebr export — экспорт настроек в JSON\n"
            f"  {ctx.prefix}zaebr import <JSON> — импорт настроек"
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
            if "action" in r:
                parts.append(f"действие {r['action']}")
            if "chats" in r:
                parts.append(f"чаты: {r['chats']}")
            if "ttl" in r:
                parts.append(f"TTL: {r['ttl']} мин")
            lines.append(f"• {uid}: {', '.join(parts)}")
        await ctx.event.reply("📋 **Реакции:**\n" + "\n".join(lines))
    elif action == "clear":
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
    elif action == "export":
        reactions = await _get_reactions(ctx.account_id)
        # Также экспортируем статус включения
        enabled = await _get_setting(ctx.account_id, "module_enabled") == "on"
        data = {
            "enabled": enabled,
            "reactions": reactions
        }
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        # Отправляем как файл или как текст (если не слишком длинный)
        if len(json_str) < 4000:
            await ctx.event.reply(f"📤 **Экспорт настроек:**\n```json\n{json_str}\n```")
        else:
            # Отправляем файлом
            await ctx.event.reply_document(
                document=json_str.encode("utf-8"),
                file_name="zaebr_export.json",
                caption="Экспорт настроек ZaebReactions"
            )
    elif action == "import":
        if len(ctx.args) < 2:
            await ctx.event.reply("❌ Укажите JSON данные для импорта.")
            return
        json_str = " ".join(ctx.args[1:])
        try:
            data = json.loads(json_str)
            if "reactions" not in data:
                await ctx.event.reply("❌ Неверный формат: отсутствует ключ 'reactions'.")
                return
            # Очищаем текущие реакции
            async with async_session_factory() as session:
                stmt = delete(Setting).where(
                    (Setting.account_id == ctx.account_id) &
                    (Setting.module == "zaeb_reactions") &
                    (Setting.key.like("user_%"))
                )
                await session.execute(stmt)
                await session.commit()
            # Импортируем новые
            for user_id, fields in data["reactions"].items():
                for field, value in fields.items():
                    await _set_reaction_field(ctx.account_id, user_id, field, value)
            # Включение/выключение
            if "enabled" in data:
                await _set_setting(ctx.account_id, "module_enabled", "on" if data["enabled"] else "off")
            await ctx.event.reply("✅ Импорт выполнен успешно.")
        except json.JSONDecodeError as e:
            await ctx.event.reply(f"❌ Ошибка парсинга JSON: {e}")
    else:
        await ctx.event.reply(f"Неизвестная подкоманда. Используйте {ctx.prefix}zaebr для справки.")


# Дополнительные команды для удобного добавления отдельных полей

@command(
    "addzaebr",
    module="zaeb_reactions",
    description="Добавить реакцию пользователю (emoji, message, action, chats, ttl)",
    admin_only=False,
)
async def cmd_addzaebr(ctx: CommandContext) -> None:
    """
    Формат: addzaebr <user> <field> <value>
    field: emoji, message, action, chats, ttl
    """
    if len(ctx.args) < 3:
        await ctx.event.reply(
            f"❌ Использование: {ctx.prefix}addzaebr <user> <emoji|message|action|chats|ttl> <значение>"
        )
        return
    user_target = ctx.args[0]
    field = ctx.args[1].lower()
    value = " ".join(ctx.args[2:])

    if field not in ("emoji", "message", "action", "chats", "ttl"):
        await ctx.event.reply("❌ Поле должно быть: emoji, message, action, chats или ttl.")
        return

    # Валидация
    if field == "emoji":
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F700-\U0001F77F"
            "\U0001F780-\U0001F7FF"
            "\U0001F800-\U0001F8FF"
            "\U0001F900-\U0001F9FF"
            "\U0001FA00-\U0001FA6F"
            "\U0001FA70-\U0001FAFF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )
        if not emoji_pattern.fullmatch(value.strip()):
            await ctx.event.reply("❌ Некорректный эмодзи.")
            return
    elif field == "action":
        if value not in ("pin", "delete", "ban", "kick"):
            await ctx.event.reply("❌ Действие должно быть: pin, delete, ban, kick.")
            return
    elif field == "ttl":
        try:
            ttl = int(value)
            if ttl <= 0:
                await ctx.event.reply("❌ TTL должно быть положительным числом (минуты).")
                return
        except ValueError:
            await ctx.event.reply("❌ TTL должно быть числом.")
            return

    await _set_reaction_field(ctx.account_id, user_target, field, value)
    await ctx.event.reply(f"✅ {field} для {user_target} установлен: {value}")


@command(
    "delzaebr",
    module="zaeb_reactions",
    description="Удалить конкретное поле реакции у пользователя",
    admin_only=False,
)
async def cmd_delzaebr(ctx: CommandContext) -> None:
    if len(ctx.args) < 2:
        await ctx.event.reply(f"❌ Использование: {ctx.prefix}delzaebr <user> <emoji|message|action|chats|ttl|all>")
        return
    user_target = ctx.args[0]
    field = ctx.args[1].lower()

    if field == "all":
        async with async_session_factory() as session:
            stmt = delete(Setting).where(
                (Setting.account_id == ctx.account_id) &
                (Setting.module == "zaeb_reactions") &
                (Setting.key.startswith(f"user_{user_target}_"))
            )
            await session.execute(stmt)
            await session.commit()
        await ctx.event.reply(f"🧹 Все реакции для {user_target} удалены.")
    elif field in ("emoji", "message", "action", "chats", "ttl"):
        if await _del_reaction_field(ctx.account_id, user_target, field):
            await ctx.event.reply(f"✅ {field} для {user_target} удалён.")
        else:
            await ctx.event.reply(f"❌ {field} для {user_target} не найден.")
    else:
        await ctx.event.reply("❌ Поле должно быть: emoji, message, action, chats, ttl или all.")


# Команды для совместимости (оставляем старые, но они теперь перенаправляют на addzaebr)
@command(
    "zaebr_emoji",
    module="zaeb_reactions",
    description="Быстро установить эмодзи (устаревшая, используйте addzaebr)",
    admin_only=False,
)
async def cmd_zaebr_emoji(ctx: CommandContext) -> None:
    if len(ctx.args) < 2:
        await ctx.event.reply(f"Использование: {ctx.prefix}zaebr_emoji <user> <emoji>")
        return
    user_target = ctx.args[0]
    emoji = ctx.args[1]
    await _set_reaction_field(ctx.account_id, user_target, "emoji", emoji)
    await ctx.event.reply(f"✅ Эмодзи для {user_target} установлен: {emoji}")


@command(
    "zaebr_message",
    module="zaeb_reactions",
    description="Быстро установить автоответ (устаревшая)",
    admin_only=False,
)
async def cmd_zaebr_message(ctx: CommandContext) -> None:
    if len(ctx.args) < 2:
        await ctx.event.reply(f"Использование: {ctx.prefix}zaebr_message <user> <сообщение>")
        return
    user_target = ctx.args[0]
    message = " ".join(ctx.args[1:])
    await _set_reaction_field(ctx.account_id, user_target, "message", message)
    await ctx.event.reply(f"✅ Автоответ для {user_target} установлен:\n💬 \"{message}\"")


@command(
    "zaebr_reaction",
    module="zaeb_reactions",
    description="Быстрая реакция (ручная)",
    admin_only=False,
)
async def cmd_zaebr_reaction(ctx: CommandContext) -> None:
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
    stats = await _get_stats(ctx.account_id)
    if not stats:
        await ctx.event.reply("📊 Статистика пуста.")
        return
    lines = [f"• {uid}: {count} активаций" for uid, count in sorted(stats.items(), key=lambda x: -x[1])]
    await ctx.event.reply("📊 **Статистика активаций:**\n" + "\n".join(lines[:20]))


@command(
    "zaebr_resetstats",
    module="zaeb_reactions",
    description="Сбросить статистику",
    admin_only=False,
)
async def cmd_zaebr_resetstats(ctx: CommandContext) -> None:
    async with async_session_factory() as session:
        stmt = delete(Setting).where(
            (Setting.account_id == ctx.account_id) &
            (Setting.module == "zaeb_reactions") &
            (Setting.key.like("stat_%"))
        )
        await session.execute(stmt)
        await session.commit()
    await ctx.event.reply("🧹 Статистика сброшена.")
