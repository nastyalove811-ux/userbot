"""
Модуль ChatStats — анализ последних N сообщений чата. Не требует прав
администратора: используется обычное чтение истории сообщений.
"""
from __future__ import annotations

import collections
import datetime as dt

from app.modules.base import CommandContext, command
from app.modules.core import get_setting
from app.redis_client import cache_get, cache_set

CACHE_TTL = 3600  # 1 час


@command("chatstats", module="chatstats", description="Статистика последних N сообщений чата")
async def cmd_chatstats(ctx: CommandContext) -> None:
    default_count = int(await get_setting(ctx.account_id, "chatstats", "count", "1000"))
    count = int(ctx.args[0]) if ctx.args and ctx.args[0].isdigit() else default_count

    chat = await ctx.event.get_chat()
    cache_key = f"chatstats:{chat.id}:{count}"
    cached = await cache_get(cache_key)
    if cached:
        await ctx.event.reply(cached)
        return

    type_counter: collections.Counter[str] = collections.Counter()
    author_counter: collections.Counter[int] = collections.Counter()
    author_names: dict[int, str] = {}
    hour_counter: collections.Counter[int] = collections.Counter()
    total_media_bytes = 0
    first_date: dt.datetime | None = None
    last_date: dt.datetime | None = None
    total = 0

    async for msg in ctx.client.iter_messages(chat, limit=count):
        total += 1
        first_date = msg.date if first_date is None or msg.date < first_date else first_date
        last_date = msg.date if last_date is None or msg.date > last_date else last_date
        hour_counter[msg.date.hour] += 1

        if msg.photo:
            type_counter["фото"] += 1
        elif msg.video:
            type_counter["видео"] += 1
        elif msg.voice:
            type_counter["голосовые"] += 1
        elif msg.audio:
            type_counter["аудио"] += 1
        elif msg.sticker:
            type_counter["стикеры"] += 1
        elif msg.gif:
            type_counter["анимации"] += 1
        elif msg.document:
            type_counter["документы"] += 1
        elif msg.message:
            type_counter["текст"] += 1
        else:
            type_counter["прочее"] += 1

        if msg.file and msg.file.size:
            total_media_bytes += msg.file.size

        if msg.sender_id:
            author_counter[msg.sender_id] += 1
            if msg.sender_id not in author_names:
                sender = await msg.get_sender()
                author_names[msg.sender_id] = getattr(sender, "first_name", None) or str(msg.sender_id)

    if total == 0:
        await ctx.event.reply("Сообщений не найдено.")
        return

    lines = [f"📊 Статистика последних {total} сообщений:"]
    lines.append("\n📁 По типам:")
    for type_name, cnt in type_counter.most_common():
        lines.append(f"  • {type_name}: {cnt} ({cnt / total * 100:.1f}%)")

    lines.append(f"\n💾 Объём медиа: {total_media_bytes / (1024 * 1024):.1f} МБ")

    lines.append("\n🏆 Топ-5 авторов:")
    for author_id, cnt in author_counter.most_common(5):
        lines.append(f"  • {author_names.get(author_id, author_id)}: {cnt}")

    if first_date and last_date:
        lines.append(f"\n🗓 Период: {first_date:%d.%m.%Y} — {last_date:%d.%m.%Y}")

    if hour_counter:
        peak_hour, peak_count = hour_counter.most_common(1)[0]
        lines.append(f"⏰ Пик активности: {peak_hour}:00 ({peak_count} сообщ.)")

    result_text = "\n".join(lines)
    await cache_set(cache_key, result_text, CACHE_TTL)
    await ctx.event.reply(result_text)
