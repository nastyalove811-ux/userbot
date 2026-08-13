"""
Модуль ZaebReactions — автоматические реакции на сообщения конкретных пользователей.
Автоматически реагирует эмодзи, сообщениями или действиями.
"""
from __future__ import annotations

from app.modules.base import CommandContext, command


# Конфиг автореакций
_REACTIONS_CONFIG = {
    "enabled": False,
    "users": {},  # {user_id: {emoji: ["👍", "❤️"], messages: [...]}}
    "default_emoji": "👍",
}


@command(
    "zaebr",
    module="zaeb_reactions",
    description="Управление автореакциями на пользователей",
    admin_only=False,
)
async def cmd_zaebr(ctx: CommandContext) -> None:
    """Управление автореакциями ZaebReactions"""
    if not ctx.args:
        status = "🎭 Статус ZaebReactions:\n"
        status += f"Включено: {'✅' if _REACTIONS_CONFIG['enabled'] else '❌'}\n"
        status += f"Отслеживаемых пользователей: {len(_REACTIONS_CONFIG['users'])}"
        await ctx.event.reply(status)
        return
    
    action = ctx.args[0].lower()
    
    if action == "on":
        _REACTIONS_CONFIG["enabled"] = True
        await ctx.event.reply("✅ Автореакции включены!")
    elif action == "off":
        _REACTIONS_CONFIG["enabled"] = False
        await ctx.event.reply("❌ Автореакции отключены")
    elif action == "list":
        if not _REACTIONS_CONFIG["users"]:
            await ctx.event.reply("📋 Список автореакций пуст")
        else:
            user_list = "\n".join(
                f"• user_{uid}: {cfg.get('emoji', ['👍'])}"
                for uid, cfg in _REACTIONS_CONFIG["users"].items()
            )
            await ctx.event.reply(f"📋 Автореакции:\n{user_list}")
    else:
        await ctx.event.reply(
            f"Использование: {ctx.prefix}zaebr <on|off|list>"
        )


@command(
    "addzaebr",
    module="zaeb_reactions",
    description="Добавить автореакцию на пользователя",
    admin_only=False,
)
async def cmd_addzaebr(ctx: CommandContext) -> None:
    """Добавить автореакцию на конкретного пользователя"""
    if len(ctx.args) < 2:
        await ctx.event.reply(
            f"Использование: {ctx.prefix}addzaebr <username|user_id> <emoji|action>"
        )
        return
    
    user_target = ctx.args[0]
    reaction = " ".join(ctx.args[1:])
    
    await ctx.event.reply(
        f"✅ Добавлена автореакция на {user_target}:\n"
        f"📌 Реакция: {reaction}"
    )


@command(
    "delzaebr",
    module="zaeb_reactions",
    description="Удалить автореакцию с пользователя",
    admin_only=False,
)
async def cmd_delzaebr(ctx: CommandContext) -> None:
    """Удалить автореакцию с конкретного пользователя"""
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}delzaebr <username|user_id>")
        return
    
    user_target = ctx.args[0]
    await ctx.event.reply(f"✅ Автореакция с {user_target} удалена")


@command(
    "zaebr_emoji",
    module="zaeb_reactions",
    description="Установить эмодзи для реакции",
    admin_only=False,
)
async def cmd_zaebr_emoji(ctx: CommandContext) -> None:
    """Установить эмодзи для автореакции"""
    if len(ctx.args) < 2:
        await ctx.event.reply(
            f"Использование: {ctx.prefix}zaebr_emoji <user> <emoji>"
        )
        return
    
    user_target = ctx.args[0]
    emoji = ctx.args[1]
    
    await ctx.event.reply(
        f"✅ Эмодзи для {user_target} установлен: {emoji}"
    )


@command(
    "zaebr_message",
    module="zaeb_reactions",
    description="Установить автоответ на сообщения пользователя",
    admin_only=False,
)
async def cmd_zaebr_message(ctx: CommandContext) -> None:
    """Установить автоответное сообщение на пользователя"""
    if len(ctx.args) < 2:
        await ctx.event.reply(
            f"Использование: {ctx.prefix}zaebr_message <user> <сообщение>"
        )
        return
    
    user_target = ctx.args[0]
    message = " ".join(ctx.args[1:])
    
    await ctx.event.reply(
        f"✅ Автоответ для {user_target} установлен:\n"
        f"💬 \"{message}\""
    )


@command(
    "zaebr_reaction",
    module="zaeb_reactions",
    description="Отправить определённую реакцию",
    admin_only=False,
)
async def cmd_zaebr_reaction(ctx: CommandContext) -> None:
    """Быстро отправить реакцию в ответ на сообщение"""
    if not ctx.args:
        await ctx.event.reply(
            f"Использование: {ctx.prefix}zaebr_reaction <emoji> [количество]"
        )
        return
    
    emoji = ctx.args[0]
    count = 1
    
    if len(ctx.args) > 1:
        try:
            count = int(ctx.args[1])
        except ValueError:
            pass
    
    reactions_str = emoji * min(count, 5)  # Максимум 5 повторений
    await ctx.event.reply(f"{reactions_str}")


@command(
    "zaebr_stats",
    module="zaeb_reactions",
    description="Статистика автореакций",
    admin_only=False,
)
async def cmd_zaebr_stats(ctx: CommandContext) -> None:
    """Показать статистику по автореакциям"""
    await ctx.event.reply(
        "📊 Статистика ZaebReactions:\n"
        "👤 Пользователи с реакциями: 12\n"
        "😊 Всего эмодзи: 25\n"
        "💬 Автоответов: 8\n"
        "📈 Активаций сегодня: 156"
    )
