"""
Модуль TagAll — массовые упоминания всех членов чата.
Позволяет упоминать больших количеств пользователей различными способами.
"""
from __future__ import annotations

from telethon.tl.types import Channel, Chat

from app.modules.base import CommandContext, command


async def _get_chat_members(ctx: CommandContext, exclude_bots: bool = False) -> list[str]:
    """Получить список всех членов чата"""
    chat = await ctx.event.get_chat()
    members = []
    
    try:
        async for member in ctx.client.iter_participants(chat):
            if exclude_bots and member.bot:
                continue
            
            # Пытаемся получить юзернейм, если его нет - пропускаем
            if member.username:
                members.append(f"@{member.username}")
            elif member.first_name:
                members.append(f"[{member.first_name}](tg://user?id={member.id})")
    except Exception:
        pass
    
    return members


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
    
    message = " ".join(ctx.args) if ctx.args else "Привет, все!"
    
    members = await _get_chat_members(ctx)
    
    if not members:
        await ctx.event.reply("❌ Не удалось получить список участников")
        return
    
    # Разбиваем на части (макс 50 упоминаний в одном сообщении)
    chunk_size = 50
    chunks = [members[i:i + chunk_size] for i in range(0, len(members), chunk_size)]
    
    for i, chunk in enumerate(chunks):
        mentions = " ".join(chunk)
        if i == 0:
            await ctx.event.respond(f"{mentions}\n\n💬 {message}")
        else:
            await ctx.event.respond(mentions)
    
    await ctx.event.delete()


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
    
    message = " ".join(ctx.args) if ctx.args else "Привет, люди!"
    
    members = await _get_chat_members(ctx, exclude_bots=True)
    
    if not members:
        await ctx.event.reply("❌ Не удалось получить список участников")
        return
    
    chunk_size = 50
    chunks = [members[i:i + chunk_size] for i in range(0, len(members), chunk_size)]
    
    for i, chunk in enumerate(chunks):
        mentions = " ".join(chunk)
        if i == 0:
            await ctx.event.respond(f"{mentions}\n\n💬 {message}")
        else:
            await ctx.event.respond(mentions)
    
    await ctx.event.delete()


@command(
    "tagrole",
    module="tagall",
    description="Упомянуть пользователей с определённой ролью",
    admin_only=False,
)
async def cmd_tagrole(ctx: CommandContext) -> None:
    """Упомянуть только пользователей с определённой ролью"""
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}tagrole <admin|user> [сообщение]")
        return
    
    role = ctx.args[0].lower()
    message = " ".join(ctx.args[1:]) if len(ctx.args) > 1 else f"Все с ролью {role}!"
    
    chat = await ctx.event.get_chat()
    members = []
    
    try:
        async for member in ctx.client.iter_participants(chat, filter=None):
            if role == "admin" and member.adminRights:
                if member.username:
                    members.append(f"@{member.username}")
            elif role == "user" and not member.adminRights and not member.creatorRights:
                if member.username:
                    members.append(f"@{member.username}")
    except Exception:
        pass
    
    if not members:
        await ctx.event.reply(f"❌ Пользователей с ролью '{role}' не найдено")
        return
    
    mentions = " ".join(members[:50])
    await ctx.event.respond(f"{mentions}\n\n💬 {message}")
    await ctx.event.delete()


@command(
    "tagadmins",
    module="tagall",
    description="Упомянуть всех администраторов",
    admin_only=False,
)
async def cmd_tagadmins(ctx: CommandContext) -> None:
    """Упомянуть только администраторов"""
    message = " ".join(ctx.args) if ctx.args else "Нужны администраторы!"
    
    chat = await ctx.event.get_chat()
    admins = []
    
    try:
        async for member in ctx.client.iter_participants(chat):
            if member.adminRights or member.creatorRights:
                if member.username:
                    admins.append(f"@{member.username}")
    except Exception:
        pass
    
    if not admins:
        await ctx.event.reply("❌ Администраторы не найдены")
        return
    
    mentions = " ".join(admins)
    await ctx.event.respond(f"{mentions}\n\n💬 {message}")
    await ctx.event.delete()


@command(
    "tagmods",
    module="tagall",
    description="Упомянуть всех модераторов",
    admin_only=False,
)
async def cmd_tagmods(ctx: CommandContext) -> None:
    """Упомянуть только модераторов"""
    message = " ".join(ctx.args) if ctx.args else "Требуется модерация!"
    
    chat = await ctx.event.get_chat()
    mods = []
    
    try:
        async for member in ctx.client.iter_participants(chat):
            # Модераторы это обычно админы без create_right
            if member.adminRights and not member.creatorRights:
                if member.username:
                    mods.append(f"@{member.username}")
    except Exception:
        pass
    
    if not mods:
        await ctx.event.reply("❌ Модераторы не найдены")
        return
    
    mentions = " ".join(mods[:50])
    await ctx.event.respond(f"{mentions}\n\n💬 {message}")
    await ctx.event.delete()


@command(
    "tagsilent",
    module="tagall",
    description="Упомянуть без уведомлений",
    admin_only=False,
)
async def cmd_tagsilent(ctx: CommandContext) -> None:
    """Упомянуть всех но без звука для них"""
    message = " ".join(ctx.args) if ctx.args else "Тихое упоминание"
    
    members = await _get_chat_members(ctx)
    
    if not members:
        await ctx.event.reply("❌ Не удалось получить список участников")
        return
    
    # Используем нулевые символы для "тихого" упоминания
    silent_mentions = " ".join(members[:30])
    await ctx.event.respond(f"‌‌‌‌{silent_mentions}\n\n💬 {message}", silent=True)
    await ctx.event.delete()


@command(
    "tagcount",
    module="tagall",
    description="Вывести количество членов чата",
    admin_only=False,
)
async def cmd_tagcount(ctx: CommandContext) -> None:
    """Показать статистику упоминаний"""
    chat = await ctx.event.get_chat()
    
    try:
        total = 0
        bots = 0
        admins = 0
        
        async for member in ctx.client.iter_participants(chat):
            total += 1
            if member.bot:
                bots += 1
            if member.adminRights or member.creatorRights:
                admins += 1
        
        humans = total - bots
        
        await ctx.event.reply(
            f"📊 Статистика чата:\n"
            f"👥 Всего пользователей: {total}\n"
            f"👤 Реальных (не ботов): {humans}\n"
            f"🤖 Ботов: {bots}\n"
            f"⭐ Администраторов: {admins}"
        )
    except Exception as e:
        await ctx.event.reply(f"❌ Ошибка при получении статистики: {str(e)}")
