"""
Обёртка над redis.asyncio для кэша, очередей задач и pub/sub-синхронизации
между веб-процессом (API) и процессом воркера.
Поддерживает работу без Redis (заглушка).
"""
from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

import redis.asyncio as redis

from app.settings import get_settings

logger = logging.getLogger("userbot.redis")

_settings = get_settings()

# Инициализируем пул и клиент только если REDIS_URL задан
if _settings.redis_url:
    _pool = redis.ConnectionPool.from_url(_settings.redis_url, decode_responses=True)
    _redis_client = redis.Redis(connection_pool=_pool)
else:
    _pool = None
    _redis_client = None
    logger.info("Redis не настроен (REDIS_URL отсутствует). Работаем в режиме заглушки.")


def get_redis() -> redis.Redis | None:
    """Возвращает клиент Redis или None, если Redis не настроен."""
    return _redis_client


# --- Кэш --------------------------------------------------------------

async def cache_set(key: str, value: Any, ttl_seconds: int | None = None) -> None:
    """Установить значение в кэш. Если Redis не настроен, ничего не делает."""
    if _redis_client is None:
        return
    r = get_redis()
    payload = json.dumps(value) if not isinstance(value, str) else value
    await r.set(key, payload, ex=ttl_seconds)


async def cache_get(key: str) -> Any | None:
    """Получить значение из кэша. Если Redis не настроен, возвращает None."""
    if _redis_client is None:
        return None
    r = get_redis()
    raw = await r.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


async def cache_delete(key: str) -> None:
    """Удалить ключ из кэша. Если Redis не настроен, ничего не делает."""
    if _redis_client is None:
        return
    r = get_redis()
    await r.delete(key)


# --- Очереди задач (например, рассылки campaigns) ----------------------

QUEUE_KEY = "queue:tasks"


async def enqueue_task(task: dict) -> None:
    """Добавить задачу в очередь. Если Redis не настроен, ничего не делает."""
    if _redis_client is None:
        return
    r = get_redis()
    await r.rpush(QUEUE_KEY, json.dumps(task))


async def dequeue_task(timeout: int = 5) -> dict | None:
    """
    Извлечь задачу из очереди (блокирующая операция).
    Если Redis не настроен, возвращает None.
    """
    if _redis_client is None:
        return None
    r = get_redis()
    result = await r.blpop(QUEUE_KEY, timeout=timeout)
    if result is None:
        return None
    _, raw = result
    return json.loads(raw)


# --- Pub/Sub для синхронизации состояния между API и воркером ----------

EVENTS_CHANNEL = "events:sync"


async def publish_event(event_type: str, payload: dict) -> None:
    """
    Опубликовать событие в канал Pub/Sub.
    Если Redis не настроен, ничего не делает.
    """
    if _redis_client is None:
        return
    r = get_redis()
    await r.publish(EVENTS_CHANNEL, json.dumps({"type": event_type, "payload": payload}))


async def subscribe_events() -> AsyncIterator[dict]:
    """
    Подписаться на события Pub/Sub (генератор).
    Если Redis не настроен, генератор завершается сразу (не выдаёт событий).
    """
    if _redis_client is None:
        # Пустой генератор
        if False:
            yield
        return
    r = get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(EVENTS_CHANNEL)
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        yield json.loads(message["data"])


# --- Хранение кодов подтверждения при подключении аккаунтов ------------

async def store_login_code_state(phone: str, state: dict, ttl_seconds: int = 300) -> None:
    """Сохранить состояние авторизации (код подтверждения). Если Redis не настроен, ничего не делает."""
    if _redis_client is None:
        return
    await cache_set(f"login:{phone}", state, ttl_seconds)


async def get_login_code_state(phone: str) -> dict | None:
    """Получить состояние авторизации. Если Redis не настроен, возвращает None."""
    if _redis_client is None:
        return None
    return await cache_get(f"login:{phone}")


async def clear_login_code_state(phone: str) -> None:
    """Очистить состояние авторизации. Если Redis не настроен, ничего не делает."""
    if _redis_client is None:
        return
    await cache_delete(f"login:{phone}")
