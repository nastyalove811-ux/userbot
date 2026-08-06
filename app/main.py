"""
FastAPI приложение — REST API для веб-панели.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_models
from app.routes import accounts, auth_routes, logs, settings_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_models()
    yield


app = FastAPI(title="Userbot Control Panel API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # сузьте до домена вашей веб-панели в продакшене
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router, prefix="/api/auth", tags=["auth"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(settings_routes.router, prefix="/api/settings", tags=["settings"])
app.include_router(logs.router, prefix="/api/logs", tags=["logs"])


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}
