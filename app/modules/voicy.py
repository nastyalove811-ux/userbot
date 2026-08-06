"""
Модуль Voicy — распознавание голосовых сообщений в текст через внешний
STT-сервис. URL и ключ задаются через настройки модуля (.settings voicy
api_url/api_key), так как выбор конкретного провайдера остаётся за
пользователем (например, self-hosted Whisper API).
"""
from __future__ import annotations

import httpx

from app.modules.base import CommandContext, command
from app.modules.core import get_setting, set_setting


async def _transcribe(audio_bytes: bytes, api_url: str, api_key: str | None) -> str:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    files = {"file": ("voice.ogg", audio_bytes, "audio/ogg")}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(api_url, headers=headers, files=files)
        resp.raise_for_status()
        data = resp.json()
        return data.get("text", "")


@command("voicy", module="voicy", description="Распознать голосовое сообщение (ответом)")
async def cmd_voicy(ctx: CommandContext) -> None:
    reply = await ctx.event.get_reply_message()
    if not reply or not (reply.voice or reply.audio):
        await ctx.event.reply(f"Использование: ответом на голосовое — {ctx.prefix}voicy")
        return

    api_url = await get_setting(ctx.account_id, "voicy", "api_url")
    if not api_url:
        await ctx.event.reply(
            "❌ Не настроен STT-сервис. Задайте: "
            f"{ctx.prefix}settings voicy api_url <URL> и (опционально) "
            f"{ctx.prefix}settings voicy api_key <ключ>"
        )
        return
    api_key = await get_setting(ctx.account_id, "voicy", "api_key")

    audio_bytes = await ctx.client.download_media(reply.voice or reply.audio, file=bytes)
    try:
        text = await _transcribe(audio_bytes, api_url, api_key)
    except httpx.HTTPError as exc:
        await ctx.event.reply(f"❌ Ошибка распознавания: {exc}")
        return

    await ctx.event.reply(f"🗣 Распознанный текст:\n{text}" if text else "Не удалось распознать текст.")


@command("autovoice", module="voicy", description="Включить/выключить авторас­познавание в чате")
async def cmd_autovoice(ctx: CommandContext) -> None:
    chat = await ctx.event.get_chat()
    current = await get_setting(ctx.account_id, "voicy", f"auto:{chat.id}", "0")
    new_value = "0" if current == "1" else "1"
    await set_setting(ctx.account_id, "voicy", f"auto:{chat.id}", new_value)
    await ctx.event.reply("🎙 Авто-распознавание " + ("включено." if new_value == "1" else "выключено."))


async def handle_auto_voice(ctx_client, account_id: int, event) -> None:
    """Вызывается диспетчером на каждое входящее голосовое в чате с включённым autovoice."""
    chat = await event.get_chat()
    enabled = await get_setting(account_id, "voicy", f"auto:{chat.id}", "0")
    if enabled != "1":
        return
    api_url = await get_setting(account_id, "voicy", "api_url")
    if not api_url:
        return
    api_key = await get_setting(account_id, "voicy", "api_key")
    audio_bytes = await ctx_client.download_media(event.voice, file=bytes)
    try:
        text = await _transcribe(audio_bytes, api_url, api_key)
    except httpx.HTTPError:
        return
    if text:
        await event.reply(f"🗣 {text}")
