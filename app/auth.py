"""
Аутентификация веб-панели.
Логин/пароль сверяются с переменными окружения ADMIN_LOGIN / ADMIN_PASSWORD.
Активная сессия хранится в Redis (session_id -> {"authenticated": true}), а
session_id передаётся клиенту в подписанной cookie.
"""
from __future__ import annotations

import secrets

from fastapi import Cookie, HTTPException, Request, status
from itsdangerous import BadSignature, URLSafeSerializer

from app.redis_client import cache_delete, cache_get, cache_set
from app.settings import get_settings

_settings = get_settings()
_serializer = URLSafeSerializer(_settings.secret_key, salt="userbot-session")

COOKIE_NAME = "userbot_session"


def _session_key(session_id: str) -> str:
    return f"web_session:{session_id}"


async def create_session() -> str:
    """Создаёт новую сессию после успешного логина и возвращает подписанный cookie-токен."""
    session_id = secrets.token_urlsafe(32)
    await cache_set(_session_key(session_id), {"authenticated": True}, ttl_seconds=_settings.session_ttl_seconds)
    return _serializer.dumps(session_id)


async def destroy_session(token: str) -> None:
    try:
        session_id = _serializer.loads(token)
    except BadSignature:
        return
    await cache_delete(_session_key(session_id))


def verify_credentials(login: str, password: str) -> bool:
    # Сравнение с постоянным временем выполнения, чтобы не давать возможности timing-атаки.
    return secrets.compare_digest(login, _settings.admin_login) and secrets.compare_digest(
        password, _settings.admin_password
    )


async def require_auth(request: Request, session_token: str | None = Cookie(default=None, alias=COOKIE_NAME)) -> None:
    """FastAPI dependency: бросает 401, если пользователь не залогинен."""
    if not session_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Не авторизован")
    try:
        session_id = _serializer.loads(session_token)
    except BadSignature:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Некорректная сессия")

    data = await cache_get(_session_key(session_id))
    if not data or not data.get("authenticated"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Сессия истекла")
