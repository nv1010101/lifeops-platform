from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import MetaData
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import Settings, get_settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def resolve_async_database_url(database_url: str) -> str:
    url = make_url(database_url)
    if url.drivername == "postgresql+asyncpg":
        return url.render_as_string(hide_password=False)
    if url.drivername == "postgres" or url.drivername.startswith("postgresql"):
        return url.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)
    return database_url


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


_engine: AsyncEngine | None = None
AsyncSessionLocal = async_sessionmaker[AsyncSession](expire_on_commit=False, autoflush=False)


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    global _engine

    if _engine is None:
        resolved_settings = settings or get_settings()
        _engine = create_async_engine(
            resolve_async_database_url(resolved_settings.database_url),
            pool_pre_ping=True,
        )
        AsyncSessionLocal.configure(bind=_engine)

    return _engine


async def close_database_engine() -> None:
    global _engine

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        AsyncSessionLocal.configure(bind=None)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    settings = request.app.state.settings
    session_factory = AsyncSessionLocal
    current_bind = session_factory.kw.get("bind")
    resolved_database_url = resolve_async_database_url(settings.database_url)

    if current_bind is None:
        get_engine(settings)
    elif current_bind.url.render_as_string(hide_password=False) != resolved_database_url:
        await close_database_engine()
        get_engine(settings)

    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
