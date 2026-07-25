"""Точка входу застосунку «Взаємодія»."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import init_models
from .routers import auth, donations, feed, funds, needs

log = logging.getLogger("vzaemodiia")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate()
    await init_models()
    if settings.is_insecure_secret:
        log.warning("SECRET_KEY не задано — використовується ключ для розробки.")
    yield


app = FastAPI(
    title=settings.app_name,
    description="Координація між військовими, волонтерами та цивільними.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(needs.router)
app.include_router(funds.router)
app.include_router(donations.router)
app.include_router(feed.router)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "app": settings.app_name}


if settings.static_dir.exists():
    app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(settings.static_dir / "index.html")
