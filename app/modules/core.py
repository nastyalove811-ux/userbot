"""
Модуль Core — базовые команды управления юзерботом.
"""
from __future__ import annotations

from sqlalchemy import delete, select

from app.db import Alias, Setting, async_session_factory
from app.modules.base import CommandContext, all_modules, command
from app.settings import get_settings

# --------------------------------------------------------------------------
# Пресеты: какие модули включены в каждом наборе
# --------------------------------------------------------------------------
PRESETS: dict[str, list[str]] = {
    "minimal": ["core", "chat", "test", "info"],
    "moderation": ["core", "chat", "admin", "purger", "welcome", "swmute"],
    "utility": ["core", "chat", "kurs", "messagetofile", "chatstats", "info", "test"],
    "full": ["*"],  # все включённые (не исключённые) модули
}


async def get_setting(account_id: int | None, module: str, key: str, default: str | None = None) -> str | None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Setting).where(
                Setting.account_id == account_id, Setting.module == module, Setting.key == key
            )
        )
        row = result.scalar_one_or_none()
        return row.value if row else default


async def set_setting(account_id: int | None, module: str, key: str, value: str) -> None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(Setting).where(
                Setting.account_id == account_id, Setting.module == module, Setting.key == key
            )
        )
        row = result.scalar_one_or_none()
        if row:
            row.value = value
        else:
            session.add(Setting(account_id=account_id, module=module, key=key, value=value))
        await session.commit()


async def get_prefix(account_id: int) -> str:
    return await get_setting(account_id, "core", "prefix", get_settings().default_prefix)


async def get_lang(account_id: int) -> str:
    return await get_setting(account_id, "core", "lang", get_settings().default_lang)


@command("help", module="core", required_right=None, description="Список модулей или справка по модулю")
async def cmd_help(ctx: CommandContext) -> None:
    from app.modules.base import all_commands  # локальный импорт во избежание цикла

    def fmt_module(name: str, command_names: list[str]) -> str:
        specs = all_commands()
        block = [f"✨ {name.upper()}"]
        for cmd_name in command_names:
            spec = specs[cmd_name]
            status = "🔒" if spec.admin_only else "🌐"
            block.append(f"  {status} {ctx.prefix}{spec.name} — {spec.description or 'без описания'}")
        return "\n".join(block)

    if ctx.args:
        module_name = ctx.args[0].lower()
        commands = all_modules().get(module_name)
        if not commands:
            available = ", ".join(sorted(all_modules().keys()))
            await ctx.event.reply(f"❌ Модуль '{module_name}' не найден.\nДоступно: {available}")
            return
        lines = [
            f"📦 Модуль: {module_name}",
            "─" * min(len(module_name) + 18, 60),
            *[f"• {ctx.prefix}{cmd} — {all_commands()[cmd].description or 'без описания'}" for cmd in commands],
        ]
        await ctx.event.reply("\n".join(lines))
        return

    modules = sorted(all_modules().items())
    lines = [
        "✨ Userbot — справка",
        "═" * 28,
        "Команды можно запускать как обычным префиксом, так и через упоминание бота / ответом.",
        "",
    ]
    for module_name, command_names in modules:
        lines.append(fmt_module(module_name, command_names))
        lines.append("")
    lines.extend([
        f"💡 Примеры: {ctx.prefix}help chat | @{ctx.prefix.strip() if ctx.prefix else 'bot'}help",
        f"📌 Подробности: {ctx.prefix}help <модуль>",
    ])
    await ctx.event.reply("\n".join(lines))


@command("settings", module="core", description="Показать/изменить настройки модуля")
async def cmd_settings(ctx: CommandContext) -> None:
    if not ctx.args:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Setting).where(Setting.account_id == ctx.account_id)
            )
            rows = result.scalars().all()
        if not rows:
            await ctx.event.reply("Настройки не заданы (используются значения по умолчанию).")
            return
        lines = ["⚙️ Текущие настройки:"]
        for row in rows:
            lines.append(f"{row.module}.{row.key} = {row.value}")
        await ctx.event.reply("\n".join(lines))
        return

    module_name = ctx.args[0]
    if len(ctx.args) >= 3:
        key, value = ctx.args[1], " ".join(ctx.args[2:])
        await set_setting(ctx.account_id, module_name, key, value)
        await ctx.event.reply(f"✅ {module_name}.{key} = {value}")
    else:
        async with async_session_factory() as session:
            result = await session.execute(
                select(Setting).where(
                    Setting.account_id == ctx.account_id, Setting.module == module_name
                )
            )
            rows = result.scalars().all()
        if not rows:
            await ctx.event.reply(f"Для модуля '{module_name}' настроек нет.")
            return
        lines = [f"⚙️ Настройки модуля {module_name}:"]
        for row in rows:
            lines.append(f"{row.key} = {row.value}")
        await ctx.event.reply("\n".join(lines))


@command("setprefix", module="core", description="Установить новый префикс команд")
async def cmd_setprefix(ctx: CommandContext) -> None:
    if not ctx.args or len(ctx.args[0]) != 1:
        await ctx.event.reply(f"Использование: {ctx.prefix}setprefix <один символ>")
        return
    await set_setting(ctx.account_id, "core", "prefix", ctx.args[0])
    await ctx.event.reply(f"✅ Новый префикс: {ctx.args[0]}")


@command("lang", module="core", description="Переключить язык интерфейса (ru/en)")
async def cmd_lang(ctx: CommandContext) -> None:
    if not ctx.args or ctx.args[0].lower() not in ("ru", "en"):
        await ctx.event.reply(f"Использование: {ctx.prefix}lang <ru|en>")
        return
    await set_setting(ctx.account_id, "core", "lang", ctx.args[0].lower())
    await ctx.event.reply(f"✅ Язык переключён: {ctx.args[0].lower()}")


@command("preset", module="core", description="Применить набор модулей")
async def cmd_preset(ctx: CommandContext) -> None:
    if not ctx.args:
        lines = ["📦 Доступные пресеты:"] + [f"• {name}" for name in PRESETS]
        await ctx.event.reply("\n".join(lines))
        return
    preset_name = ctx.args[0].lower()
    if preset_name not in PRESETS:
        await ctx.event.reply(f"Пресет '{preset_name}' не найден.")
        return
    modules = PRESETS[preset_name]
    enabled = "*" if modules == ["*"] else ",".join(modules)
    await set_setting(ctx.account_id, "core", "enabled_modules", enabled)
    await ctx.event.reply(f"✅ Применён пресет '{preset_name}': {enabled}")


@command("restart", module="core", description="Перезапустить воркер (graceful shutdown + reinit)")
async def cmd_restart(ctx: CommandContext) -> None:
    from app.worker import request_restart  # локальный импорт во избежание цикла

    await ctx.event.reply("♻️ Перезапуск воркера...")
    await request_restart()


@command("addalias", module="core", description="Создать алиас команды")
async def cmd_addalias(ctx: CommandContext) -> None:
    if len(ctx.args) < 2:
        await ctx.event.reply(f"Использование: {ctx.prefix}addalias <алиас> <команда>")
        return
    alias, target = ctx.args[0].lower(), " ".join(ctx.args[1:])
    async with async_session_factory() as session:
        session.add(Alias(account_id=ctx.account_id, alias=alias, command=target))
        await session.commit()
    await ctx.event.reply(f"✅ Алиас {ctx.prefix}{alias} -> {target}")


@command("delalias", module="core", description="Удалить алиас")
async def cmd_delalias(ctx: CommandContext) -> None:
    if not ctx.args:
        await ctx.event.reply(f"Использование: {ctx.prefix}delalias <алиас>")
        return
    alias = ctx.args[0].lower()
    async with async_session_factory() as session:
        await session.execute(
            delete(Alias).where(Alias.account_id == ctx.account_id, Alias.alias == alias)
        )
        await session.commit()
    await ctx.event.reply(f"✅ Алиас {ctx.prefix}{alias} удалён")


@command("aliases", module="core", description="Список пользовательских алиасов")
async def cmd_aliases(ctx: CommandContext) -> None:
    async with async_session_factory() as session:
        result = await session.execute(select(Alias).where(Alias.account_id == ctx.account_id))
        rows = result.scalars().all()
    if not rows:
        await ctx.event.reply("Алиасов нет.")
        return
    lines = ["🔗 Алиасы:"] + [f"{ctx.prefix}{row.alias} -> {row.command}" for row in rows]
    await ctx.event.reply("\n".join(lines))
