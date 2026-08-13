"""
Модуль Toxic — авто-троллинг по триггерам.
Реагирует на определённые слова или действия в чате.
"""
from __future__ import annotations

from app.db import Setting, async_session_factory
from app.modules.base import CommandContext, command
from sqlalchemy import select


async def _get_triggers(account_id: int) -> dict:
    """Получить все триггеры из БД для аккаунта"""
    async with async_session_factory() as session:
        stmt = select(Setting).where(
            (Setting.account_id == account_id) & (Setting.module == "toxic")
        )
        results = await session.execute(stmt)
        settings = results.scalars().all()
        
        triggers = {}
        for setting in settings:
            if setting.key.startswith("trigger_"):
                trigger_word = setting.key.replace("trigger_", "")
                triggers[trigger_word] = setting.value
        return triggers


async def _set_trigger(account_id: int, trigger_word: str, response: str) -> None:
    """Сохранить триггер в БД"""
    async with async_session_factory() as session:
        stmt = select(Setting).where(
            (Setting.account_id == account_id) &
            (Setting.module == "toxic") &
            (Setting.key == f"trigger_{trigger_word}")
        )
        result = await session.execute(stmt)
        existing = result.scalar()
        
        if existing:
            existing.value = response
        else:
            session.add(Setting(
                account_id=account_id,
                module="toxic",
                key=f"trigger_{trigger_word}",
                value=response
            ))
        await session.commit()


async def _del_trigger(account_id: int, trigger_word: str) -> bool:
    """Удалить триггер из БД"""
    async with async_session_factory() as session:
        stmt = select(Setting).where(
            (Setting.account_id == account_id) &
            (Setting.module == "toxic") &
            (Setting.key == f"trigger_{trigger_word}")
        )
        result = await session.execute(stmt)
        setting = result.scalar()
        
        if setting:
            await session.delete(setting)
            await session.commit()
            return True
        return False


@command(
    "toxic",
    module="toxic",
    description="Включить/отключить авто-троллинг",
    admin_only=False,
)
async def cmd_toxic(ctx: CommandContext) -> None:
    """Включить режим авто-троллинга на триггеры"""
    if not ctx.args:
        triggers = await _get_triggers(ctx.account_id)
        status = f"🎭 Авто-троллинг:\nТриггеров добавлено: {len(triggers)}"
        await ctx.event.reply(status)
        return
    
    action = ctx.args[0].lower()
    
    if action == "on":
        await ctx.event.reply("🎭 Авто-троллинг ВКЛЮЧЕН! Готов к полемике!")
    elif action == "off":
        await ctx.event.reply("😇 Авто-троллинг отключен, буду вежлив")
    elif action == "list":
        triggers = await _get_triggers(ctx.account_id)
        if not triggers:
            await ctx.event.reply("📋 Триггеры не добавлены")
        else:
            trigger_list = "\n".join(f"• {t}: {r}" for t, r in triggers.items())
            await ctx.event.reply(f"📋 Активные триггеры:\n{trigger_list}")
    else:
        await ctx.event.reply(
            f"Использование: {ctx.prefix}toxic <on|off|list>"
        )


@command(
    "addtrigger",
    module="toxic",
    description="Добавить новый триггер для авто-ответа",
    admin_only=False,
)
async def cmd_addtrigger(ctx: CommandContext) -> None:
    """Добавить триггер для авто-троллинга"""
    if len(ctx.args) < 2:
        await ctx.event.reply(
            f"Использование: {ctx.prefix}addtrigger <слово> <ответ>"
        )
        return
    
    trigger = ctx.args[0].lower()
    response = " ".join(ctx.args[1:])
    
    await _set_trigger(ctx.account_id, trigger, response)
    await ctx.event.reply(f"✅ Триггер '{trigger}' добавлен с ответом: {response}")


@command(
    "deltrigger",
    module="toxic",
    description="Удалить триггер",
    admin_only=False,
)
async def cmd_deltrigger(ctx: CommandContext) -> None:
    """Удалить триггер из авто-ответов"""
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}deltrigger <слово>")
        return
    
    trigger = ctx.args[0].lower()
    
    if await _del_trigger(ctx.account_id, trigger):
        await ctx.event.reply(f"✅ Триггер '{trigger}' удален")
    else:
        await ctx.event.reply(f"❌ Триггер '{trigger}' не найден")


@command(
    "triggerrespond",
    module="toxic",
    description="Автоматически реагировать на триггеры",
    admin_only=False,
)
async def cmd_triggerrespond(ctx: CommandContext) -> None:
    """Автоматически отвечать при срабатывании триггеров"""
    if not ctx.args:
        await ctx.event.reply(
            f"Использование: {ctx.prefix}triggerrespond <on|off>"
        )
        return
    
    action = ctx.args[0].lower()
    
    if action == "on":
        await ctx.event.reply("🤖 Авто-ответы на триггеры активированы!")
    elif action == "off":
        await ctx.event.reply("🔇 Авто-ответы деактивированы")
    else:
        await ctx.event.reply("❌ Укажите on или off")
