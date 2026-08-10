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

    # --- Обязательные поля (должны быть заданы в окружении) ---
    database_url: str = Field(..., env="DATABASE_URL")
    redis_url: str = Field(..., env="REDIS_URL")
    api_id: int = Field(..., env="API_ID")
    api_hash: str = Field(..., env="API_HASH")
    encryption_key: str = Field(..., env="ENCRYPTION_KEY")
    admin_id: int = Field(..., env="ADMIN_ID")
    admin_login: str = Field(..., env="ADMIN_LOGIN")
    admin_password: str = Field(..., env="ADMIN_PASSWORD")
    secret_key: str = Field(..., env="SECRET_KEY")

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
