"""
Модуль toxic — автоответы на определённые триггеры (слова, фразы) в реальном времени.
Поддерживает: добавление/удаление/список триггеров, включение/выключение модуля,
регулярные выражения, случайный выбор ответа, фоновый обработчик.
"""
from __future__ import annotations

import asyncio
import logging
import random
import re
from typing import Dict, List, Optional

from app.db import Setting, async_session_factory
from app.modules.base import CommandContext, command
from sqlalchemy import select, delete

logger = logging.getLogger(__name__)


# ---------------------- Работа с БД ----------------------

async def _get_toxic_settings(account_id: int) -> Dict[str, List[str]]:
    """
    Возвращает словарь: {триггер: [список ответов]}
    """
    async with async_session_factory() as session:
        stmt = select(Setting).where(
            (Setting.account_id == account_id) &
            (Setting.module == "toxic") &
            (Setting.key.startswith("trigger_"))
        )
        results = await session.execute(stmt)
        settings = results.scalars().all()

        triggers = {}
        for setting in settings:
            # ключ: trigger_<слово>
            trigger = setting.key.replace("trigger_", "")
            # значение может содержать несколько ответов, разделённых | (или JSON)
            # Для простоты используем разделитель |
            responses = setting.value.split("|")
            triggers[trigger] = responses
        return triggers


async def _set_toxic_trigger(account_id: int, trigger: str, responses: List[str]) -> None:
    """Сохранить триггер с ответами (объединяем через |)."""
    async with async_session_factory() as session:
        stmt = select(Setting).where(
            (Setting.account_id == account_id) &
            (Setting.module == "toxic") &
            (Setting.key == f"trigger_{trigger}")
        )
        result = await session.execute(stmt)
        existing = result.scalar()
        value = "|".join(responses)
        if existing:
            existing.value = value
        else:
            session.add(Setting(
                account_id=account_id,
                module="toxic",
                key=f"trigger_{trigger}",
                value=value
            ))
        await session.commit()


async def _del_toxic_trigger(account_id: int, trigger: str) -> bool:
    """Удалить триггер."""
    async with async_session_factory() as session:
        stmt = delete(Setting).where(
            (Setting.account_id == account_id) &
            (Setting.module == "toxic") &
            (Setting.key == f"trigger_{trigger}")
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


async def _get_toxic_enabled(account_id: int) -> bool:
    """Проверить, включён ли модуль."""
    async with async_session_factory() as session:
        stmt = select(Setting).where(
            (Setting.account_id == account_id) &
            (Setting.module == "toxic") &
            (Setting.key == "module_enabled")
        )
        result = await session.execute(stmt)
        setting = result.scalar()
        return setting.value == "on" if setting else False


async def _set_toxic_enabled(account_id: int, enabled: bool) -> None:
    """Включить/выключить модуль."""
    async with async_session_factory() as session:
        stmt = select(Setting).where(
            (Setting.account_id == account_id) &
            (Setting.module == "toxic") &
            (Setting.key == "module_enabled")
        )
        result = await session.execute(stmt)
        existing = result.scalar()
        value = "on" if enabled else "off"
        if existing:
            existing.value = value
        else:
            session.add(Setting(
                account_id=account_id,
                module="toxic",
                key="module_enabled",
                value=value
            ))
        await session.commit()


# ---------------------- Обработчик новых сообщений ----------------------

async def toxic_auto_react(event) -> None:
    """
    Этот обработчик должен быть зарегистрирован как обработчик входящих сообщений.
    Проверяет все новые сообщения на наличие триггеров и отправляет случайный ответ.
    """
    account_id = event.account_id
    # Проверяем, включён ли модуль
    if not await _get_toxic_enabled(account_id):
        return

    # Получаем текст сообщения
    text = event.text
    if not text:
        return

    # Получаем все триггеры
    triggers = await _get_toxic_settings(account_id)
    if not triggers:
        return

    # Проверяем каждый триггер (с учётом регулярных выражений)
    for trigger, responses in triggers.items():
        # Если триггер начинается с 'regex:' — используем регулярку
        if trigger.startswith("regex:"):
            pattern = trigger[6:]  # убираем 'regex:'
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    # Выбираем случайный ответ
                    answer = random.choice(responses)
                    await event.reply(answer)
                    # Логируем срабатывание
                    logger.info(f"Toxic сработал по регулярке '{pattern}' для {event.sender_id}")
                    break  # не реагируем на другие триггеры в этом сообщении
            except re.error:
                # Некорректная регулярка — пропускаем
                continue
        else:
            # Обычное точное совпадение (или частичное)
            # Можно сделать проверку на вхождение
            if trigger.lower() in text.lower():
                answer = random.choice(responses)
                await event.reply(answer)
                logger.info(f"Toxic сработал по триггеру '{trigger}' для {event.sender_id}")
                break


# ---------------------- Команды управления ----------------------

@command(
    "addtoxic",
    module="toxic",
    description="Добавить триггер с ответом (можно несколько ответов через |)",
    admin_only=False,
)
async def cmd_addtoxic(ctx: CommandContext) -> None:
    """
    Использование: addtoxic <триггер> <ответ1|ответ2|...>
    Для регулярного выражения: addtoxic regex:<паттерн> <ответ1|...>
    """
    if len(ctx.args) < 2:
        await ctx.event.reply(
            f"❌ Использование: {ctx.prefix}addtoxic <триггер> <ответ1|ответ2|...>"
        )
        return

    trigger = ctx.args[0]
    responses_str = " ".join(ctx.args[1:])
    responses = [r.strip() for r in responses_str.split("|") if r.strip()]

    if not responses:
        await ctx.event.reply("❌ Нужно указать хотя бы один ответ.")
        return

    # Сохраняем
    await _set_toxic_trigger(ctx.account_id, trigger, responses)
    await ctx.event.reply(
        f"✅ Триггер '{trigger}' добавлен с {len(responses)} ответами."
    )


@command(
    "deltoxic",
    module="toxic",
    description="Удалить триггер",
    admin_only=False,
)
async def cmd_deltoxic(ctx: CommandContext) -> None:
    """Использование: deltoxic <триггер>"""
    if not ctx.args:
        await ctx.event.reply(f"❌ Использование: {ctx.prefix}deltoxic <триггер>")
        return

    trigger = ctx.args[0]
    if await _del_toxic_trigger(ctx.account_id, trigger):
        await ctx.event.reply(f"✅ Триггер '{trigger}' удалён.")
    else:
        await ctx.event.reply(f"❌ Триггер '{trigger}' не найден.")


@command(
    "listtoxic",
    module="toxic",
    description="Показать список всех триггеров",
    admin_only=False,
)
async def cmd_listtoxic(ctx: CommandContext) -> None:
    """Показать все триггеры и их ответы."""
    triggers = await _get_toxic_settings(ctx.account_id)
    if not triggers:
        await ctx.event.reply("📋 Список триггеров пуст.")
        return

    lines = []
    for trigger, responses in triggers.items():
        answers = ", ".join(responses[:3])  # покажем первые 3
        if len(responses) > 3:
            answers += f" ... (+{len(responses)-3})"
        lines.append(f"• {trigger}: {answers}")

    await ctx.event.reply("📋 **Триггеры:**\n" + "\n".join(lines))


@command(
    "toxic",
    module="toxic",
    description="Включить/выключить автоответы",
    admin_only=False,
)
async def cmd_toxic(ctx: CommandContext) -> None:
    """
    Использование: toxic <on|off|status>
    """
    if not ctx.args:
        enabled = await _get_toxic_enabled(ctx.account_id)
        await ctx.event.reply(f"Статус Toxic: {'✅ Включён' if enabled else '❌ Выключен'}")
        return

    action = ctx.args[0].lower()
    if action == "on":
        await _set_toxic_enabled(ctx.account_id, True)
        await ctx.event.reply("✅ Toxic включён.")
    elif action == "off":
        await _set_toxic_enabled(ctx.account_id, False)
        await ctx.event.reply("❌ Toxic выключен.")
    else:
        await ctx.event.reply(f"Использование: {ctx.prefix}toxic <on|off|status>")
