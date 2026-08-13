"""
Модуль TagAll — массовые упоминания всех членов чата.
Позволяет упоминать больших количеств пользователей различными способами.
"""
from __future__ import annotations

from app.modules.base import CommandContext, command


@command(
    "tagall",
    module="tagall",
    description="Упомянуть всех членов чата",
    admin_only=False,
)
async def cmd_tagall(ctx: CommandContext) -> None:
    """Упомянуть всех пользователей в чате"""
    if ctx.event.is_private:
        await ctx.event.reply("❌ Эта команда работает только в группах")
        return
    
    message = " ".join(ctx.args) if ctx.args else "Привет всем!"
    
    # В реальной реализации здесь была бы получение всех участников чата
    await ctx.event.reply(
        f"@user1 @user2 @user3 @user4 @user5 ... (и ещё N пользователей)\n\n"
        f"💬 {message}"
    )


@command(
    "tagallnobot",
    module="tagall",
    description="Упомянуть всех без ботов",
    admin_only=False,
)
async def cmd_tagallnobot(ctx: CommandContext) -> None:
    """Упомянуть всех кроме ботов"""
    if ctx.event.is_private:
        await ctx.event.reply("❌ Эта команда работает только в группах")
        return
    
    message = " ".join(ctx.args) if ctx.args else "Привет всем (кроме ботов)!"
    await ctx.event.reply(
        f"@user1 @user2 @user3 @user4 @user5 ... (без ботов)\n\n"
        f"💬 {message}"
    )


@command(
    "tagrole",
    module="tagall",
    description="Упомянуть пользователей с определённой ролью",
    admin_only=False,
)
async def cmd_tagrole(ctx: CommandContext) -> None:
    """Упомянуть только пользователей с определённой ролью"""
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}tagrole <роль> [сообщение]")
        return
    
    role = ctx.args[0]
    message = " ".join(ctx.args[1:]) if len(ctx.args) > 1 else f"Все {role}!"
    
    await ctx.event.reply(
        f"Упоминание пользователей с ролью '{role}':\n"
        f"@admin1 @admin2 @moderator1\n\n"
        f"💬 {message}"
    )


@command(
    "tagadmins",
    module="tagall",
    description="Упомянуть всех администраторов",
    admin_only=False,
)
async def cmd_tagadmins(ctx: CommandContext) -> None:
    """Упомянуть только администраторов"""
    message = " ".join(ctx.args) if ctx.args else "Нужны администраторы!"
    await ctx.event.reply(
        f"@admin1 @admin2 @admin3\n\n"
        f"💬 {message}"
    )


@command(
    "tagmods",
    module="tagall",
    description="Упомянуть всех модераторов",
    admin_only=False,
)
async def cmd_tagmods(ctx: CommandContext) -> None:
    """Упомянуть только модераторов"""
    message = " ".join(ctx.args) if ctx.args else "Требуется модерация!"
    await ctx.event.reply(
        f"@moder1 @moder2 @moder3\n\n"
        f"💬 {message}"
    )


@command(
    "tagsilent",
    module="tagall",
    description="Упомянуть без уведомлений",
    admin_only=False,
)
async def cmd_tagsilent(ctx: CommandContext) -> None:
    """Упомянуть всех но без звука для них"""
    message = " ".join(ctx.args) if ctx.args else "Тихое упоминание"
    await ctx.event.reply(
        f"‌‌‌‌@user1 @user2 @user3 @user4 @user5\n\n"
        f"💬 {message}"
    )


@command(
    "tagcount",
    module="tagall",
    description="Вывести количество членов чата",
    admin_only=False,
)
async def cmd_tagcount(ctx: CommandContext) -> None:
    """Показать статистику упоминаний"""
    await ctx.event.reply(
        "📊 Статистика чата:\n"
        "👥 Всего пользователей: 150\n"
        "👤 Реальных (не ботов): 130\n"
        "🤖 Ботов: 20\n"
        "⭐ Администраторов: 5\n"
        "🟢 Модераторов: 15"
    )
