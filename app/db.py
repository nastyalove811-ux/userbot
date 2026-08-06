"""
Подключение к PostgreSQL и ORM-модели (SQLAlchemy 2.0, async).
"""
from __future__ import annotations

import datetime as dt
from typing import AsyncIterator

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.settings import get_settings


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------
# Аккаунты и сессии
# --------------------------------------------------------------------------

class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(32), unique=True)
    session_string: Mapped[str | None] = mapped_column(Text)  # зашифровано (Fernet)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    bot_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    username: Mapped[str | None] = mapped_column(String(64))
    user_id: Mapped[int | None] = mapped_column(BigInteger)
    premium: Mapped[bool] = mapped_column(Boolean, default=False)
    about: Mapped[str | None] = mapped_column(Text)
    registration_date: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    dialogs_count: Mapped[int] = mapped_column(Integer, default=0)
    groups_count: Mapped[int] = mapped_column(Integer, default=0)
    channels_count: Mapped[int] = mapped_column(Integer, default=0)
    last_sync: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    device_model: Mapped[str | None] = mapped_column(String(128))
    platform: Mapped[str | None] = mapped_column(String(64))
    app_version: Mapped[str | None] = mapped_column(String(32))
    ip: Mapped[str | None] = mapped_column(String(64))
    country: Mapped[str | None] = mapped_column(String(64))
    last_active: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)


# --------------------------------------------------------------------------
# Настройки / алиасы / логи
# --------------------------------------------------------------------------

class Setting(Base):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("account_id", "module", "key", name="uq_settings"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), nullable=True)
    module: Mapped[str] = mapped_column(String(64))
    key: Mapped[str] = mapped_column(String(64))
    value: Mapped[str | None] = mapped_column(Text)


class Alias(Base):
    __tablename__ = "aliases"
    __table_args__ = (UniqueConstraint("account_id", "alias", name="uq_alias"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    alias: Mapped[str] = mapped_column(String(64))
    command: Mapped[str] = mapped_column(String(256))


class LogEntry(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64))
    chat_id: Mapped[int | None] = mapped_column(BigInteger)
    user_id: Mapped[int | None] = mapped_column(BigInteger)
    message: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# --------------------------------------------------------------------------
# Функциональные модули
# --------------------------------------------------------------------------

class ProfileBackup(Base):
    __tablename__ = "profile_backups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    original_first_name: Mapped[str | None] = mapped_column(String(128))
    original_last_name: Mapped[str | None] = mapped_column(String(128))
    original_about: Mapped[str | None] = mapped_column(Text)
    original_avatar_file_id: Mapped[str | None] = mapped_column(Text)
    cloned_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    restored_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class Streak(Base):
    __tablename__ = "streaks"
    __table_args__ = (UniqueConstraint("account_id", "contact_id", name="uq_streak"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    contact_id: Mapped[int] = mapped_column(BigInteger)
    original_first_name: Mapped[str | None] = mapped_column(String(128))
    original_last_name: Mapped[str | None] = mapped_column(String(128))
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_my_message_date: Mapped[dt.date | None] = mapped_column(DateTime(timezone=True))
    last_their_message_date: Mapped[dt.date | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SwMute(Base):
    __tablename__ = "swmute"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    muted_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PingBot(Base):
    __tablename__ = "ping_bots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    bot_username: Mapped[str] = mapped_column(String(64))
    ping_text: Mapped[str] = mapped_column(Text)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=300)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=15)
    is_online: Mapped[bool | None] = mapped_column(Boolean)


class BannedWord(Base):
    __tablename__ = "banned_words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    word: Mapped[str] = mapped_column(String(256))


class WelcomeSettings(Base):
    __tablename__ = "welcome_settings"
    __table_args__ = (UniqueConstraint("account_id", "chat_id", name="uq_welcome"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    welcome_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    welcome_text: Mapped[str | None] = mapped_column(Text)
    welcome_media_file_id: Mapped[str | None] = mapped_column(Text)
    goodbye_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    goodbye_text: Mapped[str | None] = mapped_column(Text)
    goodbye_media_file_id: Mapped[str | None] = mapped_column(Text)


class WordleGame(Base):
    __tablename__ = "wordle_games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    target_word: Mapped[str] = mapped_column(String(64))
    max_attempts: Mapped[int] = mapped_column(Integer, default=6)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    guessed_words: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    winner_id: Mapped[int | None] = mapped_column(BigInteger)


class TempRestriction(Base):
    __tablename__ = "temp_restrictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    type: Mapped[str] = mapped_column(String(16))  # 'ban' | 'mute'
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))


# --------------------------------------------------------------------------
# Engine / сессии
# --------------------------------------------------------------------------

_settings = get_settings()
engine = create_async_engine(_settings.database_url, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


async def init_models() -> None:
    """Создаёт таблицы, если их ещё нет. Для продакшена лучше использовать Alembic-миграции."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
