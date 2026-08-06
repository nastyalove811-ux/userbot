"""
Загрузка конфигурации из переменных окружения.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Обязательные ---
    database_url: str
    redis_url: str
    api_id: int
    api_hash: str
    encryption_key: str
    admin_id: int
    admin_login: str
    admin_password: str
    secret_key: str

    # --- Опциональные (со значениями по умолчанию) ---
    default_lang: str = "ru"
    default_prefix: str = "."
    max_spam_count: int = 50          # используется только как общий лимит массовых операций (kickall, tagall и т.п.)
    chatstats_default_count: int = 1000
    kurs_default_currency: str = "USD"
    session_ttl_seconds: int = 60 * 60 * 24 * 7  # неделя


@lru_cache
def get_settings() -> Settings:
    return Settings()
