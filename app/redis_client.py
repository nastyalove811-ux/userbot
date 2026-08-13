"""
Обёртка над redis.asyncio для кэша, очередей задач и pub/sub-синхронизации
между веб-процессом (API) и процессом воркера.
Поддерживает работу без Redis за счёт in-memory fallback.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator

import redis.asyncio as redis
from redis.exceptions import ConnectionError as RedisConnectionError

from app.settings import get_settings

logger = logging.getLogger("userbot.redis")

_settings = get_settings()
_memory_cache: dict[str, tuple[Any, float | None]] = {}
_memory_lock = asyncio.Lock()


# Инициализируем пул и клиент только если REDIS_URL задан.
# Если Redis недоступен или не настроен, используем in-memory fallback.
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


async def _memory_set(key: str, value: Any, ttl_seconds: int | None = None) -> None:
    async with _memory_lock:
        expires_at = time.monotonic() + ttl_seconds if ttl_seconds is not None else None
        _memory_cache[key] = (value, expires_at)


async def _memory_get(key: str) -> Any | None:
    async with _memory_lock:
        item = _memory_cache.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at is not None and time.monotonic() > expires_at:
            _memory_cache.pop(key, None)
            return None
        return value


async def _memory_delete(key: str) -> None:
    async with _memory_lock:
        _memory_cache.pop(key, None)


async def _safe_redis_call(action: str, fn, *args, **kwargs):
    if _redis_client is None:
        return None
    try:
        return await fn(*args, **kwargs)
    except RedisConnectionError:
        logger.warning("Redis недоступен, включён in-memory fallback для %s", action)
        return None
    except OSError:
        logger.warning("Redis недоступен, включён in-memory fallback для %s", action)
        return None


# --- Кэш --------------------------------------------------------------

async def cache_set(key: str, value: Any, ttl_seconds: int | None = None) -> None:
    """Установить значение в кэш. Если Redis недоступен, используется in-memory fallback."""
    if _redis_client is None:
        await _memory_set(key, value, ttl_seconds)
        return
    r = get_redis()
    payload = json.dumps(value) if not isinstance(value, str) else value
    try:
        await r.set(key, payload, ex=ttl_seconds)
    except (RedisConnectionError, OSError):
        logger.warning("Redis недоступен, сохраняем %s в in-memory fallback", key)
        await _memory_set(key, value, ttl_seconds)


async def cache_get(key: str) -> Any | None:
    """Получить значение из кэша. Если Redis недоступен, используется in-memory fallback."""
    if _redis_client is None:
        value = await _memory_get(key)
        if value is None:
            return None
        return value
    r = get_redis()
    try:
        raw = await r.get(key)
    except (RedisConnectionError, OSError):
        logger.warning("Redis недоступен, читаем %s из in-memory fallback", key)
        value = await _memory_get(key)
        if value is None:
            return None
        return value
    if raw is None:
        return await _memory_get(key)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


async def cache_delete(key: str) -> None:
    """Удалить ключ из кэша. Если Redis недоступен, используется in-memory fallback."""
    if _redis_client is None:
        await _memory_delete(key)
        return
    r = get_redis()
    try:
        await r.delete(key)
    except (RedisConnectionError, OSError):
        logger.warning("Redis недоступен, удаляем %s из in-memory fallback", key)
        await _memory_delete(key)


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
