"""
Обёртка над redis.asyncio для кэша, очередей задач и pub/sub-синхронизации
между веб-процессом (API) и процессом воркера.
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator

import redis.asyncio as redis

from app.settings import get_settings

_settings = get_settings()
_pool = redis.ConnectionPool.from_url(_settings.redis_url, decode_responses=True)


def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=_pool)


# --- Кэш --------------------------------------------------------------

async def cache_set(key: str, value: Any, ttl_seconds: int | None = None) -> None:
    r = get_redis()
    payload = json.dumps(value) if not isinstance(value, str) else value
    await r.set(key, payload, ex=ttl_seconds)


async def cache_get(key: str) -> Any | None:
    r = get_redis()
    raw = await r.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


async def cache_delete(key: str) -> None:
    r = get_redis()
    await r.delete(key)


# --- Очереди задач (например, рассылки campaigns) ----------------------

QUEUE_KEY = "queue:tasks"


async def enqueue_task(task: dict) -> None:
    r = get_redis()
    await r.rpush(QUEUE_KEY, json.dumps(task))


async def dequeue_task(timeout: int = 5) -> dict | None:
    r = get_redis()
    result = await r.blpop(QUEUE_KEY, timeout=timeout)
    if result is None:
        return None
    _, raw = result
    return json.loads(raw)


# --- Pub/Sub для синхронизации состояния между API и воркером ----------

EVENTS_CHANNEL = "events:sync"


async def publish_event(event_type: str, payload: dict) -> None:
    r = get_redis()
    await r.publish(EVENTS_CHANNEL, json.dumps({"type": event_type, "payload": payload}))


async def subscribe_events() -> AsyncIterator[dict]:
    r = get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(EVENTS_CHANNEL)
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        yield json.loads(message["data"])


# --- Хранение кодов подтверждения при подключении аккаунтов ------------

async def store_login_code_state(phone: str, state: dict, ttl_seconds: int = 300) -> None:
    await cache_set(f"login:{phone}", state, ttl_seconds)


async def get_login_code_state(phone: str) -> dict | None:
    return await cache_get(f"login:{phone}")


async def clear_login_code_state(phone: str) -> None:
    await cache_delete(f"login:{phone}")
