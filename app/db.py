"""Асинхронне підключення до бази та фабрика сесій."""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings

engine = create_async_engine(settings.database_url, echo=False, future=True)

SessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_models() -> None:
    """Створює таблиці. Для реального проєкту тут була б Alembic-міграція."""
    from . import models  # noqa: F401  (реєструє моделі в метаданих)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
