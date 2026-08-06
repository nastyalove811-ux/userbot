"""
Модуль Wordle — классическая игра "угадай слово" в чате.
Права по умолчанию: играть могут все участники (доступность настраивается).
"""
from __future__ import annotations

import random

from sqlalchemy import select

from app.db import WordleGame, async_session_factory
from app.modules.base import CommandContext, command
from app.modules.core import get_setting, set_setting

_WORDS = [
    "python", "телега", "ракета", "музыка", "экран", "клавиша",
    "звезда", "облако", "дорога", "камень", "ветер", "солнце",
]


def _score_guess(target: str, guess: str) -> str:
    """Возвращает строку эмодзи-подсказок: 🟩 верно, 🟨 не там, ⬛ отсутствует."""
    result = ["⬛"] * len(guess)
    target_chars = list(target)

    for i, ch in enumerate(guess):
        if i < len(target) and ch == target[i]:
            result[i] = "🟩"
            target_chars[i] = None

    for i, ch in enumerate(guess):
        if result[i] == "🟩":
            continue
        if ch in target_chars:
            result[i] = "🟨"
            target_chars[target_chars.index(ch)] = None

    return "".join(result)


@command("wordle", module="wordle", admin_only=True, description="Начать игру Wordle")
async def cmd_wordle(ctx: CommandContext) -> None:
    chat = await ctx.event.get_chat()

    async with async_session_factory() as session:
        result = await session.execute(
            select(WordleGame).where(
                WordleGame.account_id == ctx.account_id, WordleGame.chat_id == chat.id, WordleGame.is_active == True  # noqa: E712
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            await ctx.event.reply(f"🎮 Игра уже идёт! Слово из {len(existing.target_word)} букв, попыток: {existing.attempts}/{existing.max_attempts}")
            return

        word = ctx.args[0].lower() if ctx.args else random.choice(_WORDS)
        max_attempts_setting = await get_setting(ctx.account_id, "wordle", "max_attempts", "6")

        session.add(
            WordleGame(
                account_id=ctx.account_id, chat_id=chat.id, target_word=word,
                max_attempts=int(max_attempts_setting), attempts=0, guessed_words=[], is_active=True,
            )
        )
        await session.commit()

    await ctx.event.reply(f"🎮 Игра началась! Загадано слово из {len(word)} букв. Пишите варианты в чат.")


async def handle_guess(account_id: int, chat_id: int, event) -> None:
    """Вызывается диспетчером воркера на каждое обычное (не-командное) сообщение в чате с активной игрой."""
    async with async_session_factory() as session:
        result = await session.execute(
            select(WordleGame).where(
                WordleGame.account_id == account_id, WordleGame.chat_id == chat_id, WordleGame.is_active == True  # noqa: E712
            )
        )
        game = result.scalar_one_or_none()
        if not game:
            return

        guess = (event.raw_text or "").strip().lower()
        if len(guess) != len(game.target_word) or not guess.isalpha():
            return

        game.attempts += 1
        game.guessed_words = game.guessed_words + [guess]
        hint = _score_guess(game.target_word, guess)

        if guess == game.target_word:
            game.is_active = False
            game.winner_id = event.sender_id
            await session.commit()
            await event.reply(f"{hint}\n🎉 Верно! Слово: {game.target_word}")
            return

        if game.attempts >= game.max_attempts:
            game.is_active = False
            await session.commit()
            await event.reply(f"{hint}\n💀 Попытки закончились. Слово было: {game.target_word}")
            return

        await session.commit()
        await event.reply(f"{hint} ({game.attempts}/{game.max_attempts})")
