"""
Модуль Toxic — авто-троллинг по триггерам.
Реагирует на определённые слова или действия в чате.
"""
from __future__ import annotations

from app.modules.base import CommandContext, command


# Словарь триггеров и ответов
_TOXIC_TRIGGERS = {
    "привет": "👋 Привет, уёбок!",
    "привет": "Слыш, лох, не здоровайся!",
    "hi": "🚫 Нах отсюда!",
    "hello": "💀 Убирайся отсюда!",
}

_TOXIC_RESPONSES = [
    "А ты кто вообще?",
    "Иди отсюда, плешивый!",
    "🤡 Ты уже надоел!",
    "Молчи, клоун!",
    "Пошел нах!",
]


@command(
    "toxic",
    module="toxic",
    description="Включить/отключить авто-троллинг",
    admin_only=False,
)
async def cmd_toxic(ctx: CommandContext) -> None:
    """Включить режим авто-троллинга на триггеры"""
    if not ctx.args:
        await ctx.event.reply(
            "Использование: {ctx.prefix}toxic <on|off|list>\n"
            "on — включить\noff — отключить\nlist — список триггеров"
        )
        return
    
    action = ctx.args[0].lower()
    
    if action == "on":
        await ctx.event.reply("🎭 Авто-троллинг ВКЛЮЧЕН! Готов к полемике!")
    elif action == "off":
        await ctx.event.reply("😇 Авто-троллинг отключен, буду вежлив")
    elif action == "list":
        triggers_list = "\n".join(f"• {trigger}" for trigger in _TOXIC_TRIGGERS.keys())
        await ctx.event.reply(f"📋 Активные триггеры:\n{triggers_list}")
    else:
        await ctx.event.reply(f"❌ Неизвестная команда: {action}")


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
    
    _TOXIC_TRIGGERS[trigger] = response
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
    
    if trigger in _TOXIC_TRIGGERS:
        del _TOXIC_TRIGGERS[trigger]
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
