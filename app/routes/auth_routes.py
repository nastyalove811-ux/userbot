from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from app.auth import COOKIE_NAME, create_session, destroy_session, verify_credentials

router = APIRouter()


class LoginRequest(BaseModel):
    login: str
    password: str


@router.post("/login")
async def login(payload: LoginRequest, response: Response) -> dict:
    if not verify_credentials(payload.login, payload.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Неверный логин или пароль")
    token = await create_session()
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, samesite="lax", secure=True, max_age=60 * 60 * 24 * 7
    )
    return {"status": "ok"}


@router.post("/logout")
async def logout(response: Response, session_token: str | None = None) -> dict:
    if session_token:
        await destroy_session(session_token)
    response.delete_cookie(COOKIE_NAME)
    return {"status": "ok"}
