"""
Загрузка конфигурации из переменных окружения.
Поддерживаются как переменные в верхнем регистре (DATABASE_URL),
так и в нижнем (database_url), приоритет у явно указанных в env.
"""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Поля с безопасными значениями по умолчанию для локальной разработки ---
    # При отсутствии .env или Redis приложение всё равно стартует, но Telegram-API
    # и сессии будут работать только после корректной настройки окружения.
    database_url: str = Field(default="sqlite+aiosqlite:///./userbot.db", env="DATABASE_URL")
    redis_url: str | None = Field(default=None, env="REDIS_URL")
    api_id: int = Field(default=0, env="API_ID")
    api_hash: str = Field(default="", env="API_HASH")
    encryption_key: str = Field(default="", env="ENCRYPTION_KEY")
    admin_id: int = Field(default=1, env="ADMIN_ID")
    admin_login: str = Field(default="admin", env="ADMIN_LOGIN")
    admin_password: str = Field(default="admin", env="ADMIN_PASSWORD")
    secret_key: str = Field(default="dev-secret-key", env="SECRET_KEY")

    # --- Опциональные поля со значениями по умолчанию ---
    default_lang: str = "ru"
    default_prefix: str = "."
    max_spam_count: int = 50
    chatstats_default_count: int = 1000
    kurs_default_currency: str = "USD"
    session_ttl_seconds: int = 60 * 60 * 24 * 7  # 7 дней


@lru_cache
def get_settings() -> Settings:
    """
    Возвращает закэшированный экземпляр настроек.
    При изменении переменных окружения нужно перезапустить приложение.
    """
    return Settings()
