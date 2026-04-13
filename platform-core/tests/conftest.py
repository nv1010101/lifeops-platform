from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
import getpass
import os
import subprocess
import sys
import uuid

import asyncpg
import pytest
import pytest_asyncio
from fastapi import APIRouter, HTTPException, Query
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings, get_settings
from app.database import close_database_engine, resolve_async_database_url
from app.dependencies import RequestContextDependency
from app.main import create_app
from app.model_registry import load_all_models


TESTS_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
NO_DB_DATABASE_URL = "postgresql+asyncpg://unused:unused@127.0.0.1:1/lifeops_unused"


def build_test_settings(*, database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        app_base_url="http://testserver",
        database_url=database_url,
        jwt_secret="test-secret",
    )


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Generator[None, None, None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    return build_test_settings(database_url=NO_DB_DATABASE_URL)


@pytest.fixture(autouse=True)
def ensure_models_loaded() -> None:
    load_all_models()


@pytest.fixture
def client(settings: Settings) -> Generator[TestClient, None, None]:
    app = create_app(settings=settings)
    router = APIRouter()

    @router.get("/test/context")
    def read_request_context(request_context: RequestContextDependency) -> dict[str, str]:
        return {
            "request_id": request_context.request_id,
            "correlation_id": request_context.correlation_id,
        }

    @router.get("/test/http/{status_code}")
    def raise_http_error(status_code: int) -> None:
        detail_by_status = {
            400: "Bad input for test route.",
            404: "Missing test resource.",
        }
        raise HTTPException(
            status_code=status_code,
            detail=detail_by_status.get(status_code, "HTTP test error."),
        )

    @router.get("/test/validation")
    def validation_route(limit: int = Query(ge=1)) -> dict[str, int]:
        return {"limit": limit}

    @router.get("/test/crash")
    def crash_route() -> None:
        raise RuntimeError("boom")

    app.include_router(router)

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def db_settings(database_url: str) -> Settings:
    return build_test_settings(database_url=database_url)


@pytest_asyncio.fixture
async def db_client(db_settings: Settings) -> AsyncGenerator[TestClient, None]:
    app = create_app(settings=db_settings)

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _build_postgres_admin_url() -> str:
    explicit_database_url = os.environ.get("TEST_ADMIN_DATABASE_URL")
    if explicit_database_url:
        return resolve_async_database_url(explicit_database_url)

    user = os.environ.get("TEST_POSTGRES_USER", getpass.getuser())
    password = os.environ.get("TEST_POSTGRES_PASSWORD", "")
    host = os.environ.get("TEST_POSTGRES_HOST", "127.0.0.1")
    port = os.environ.get("TEST_POSTGRES_PORT", "5432")
    auth = user if not password else f"{user}:{password}"
    return f"postgresql+asyncpg://{auth}@{host}:{port}/postgres"


def _asyncpg_dsn(database_url: str) -> str:
    url = make_url(database_url)
    if url.drivername == "postgresql+asyncpg":
        return url.set(drivername="postgresql").render_as_string(hide_password=False)
    return database_url


def _build_test_database_url(database_name: str) -> str:
    admin_url = _build_postgres_admin_url()
    return admin_url.rsplit("/", maxsplit=1)[0] + f"/{database_name}"


async def _create_database(database_name: str) -> str:
    admin_connection = await asyncpg.connect(_asyncpg_dsn(_build_postgres_admin_url()))
    try:
        await admin_connection.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
        await admin_connection.execute(f'CREATE DATABASE "{database_name}"')
    finally:
        await admin_connection.close()

    return _build_test_database_url(database_name)


async def _drop_database(database_name: str) -> None:
    admin_connection = await asyncpg.connect(_asyncpg_dsn(_build_postgres_admin_url()))
    try:
        await admin_connection.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = $1 AND pid <> pg_backend_pid()
            """,
            database_name,
        )
        await admin_connection.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
    finally:
        await admin_connection.close()


@pytest_asyncio.fixture
async def database_url() -> AsyncGenerator[str, None]:
    database_name = f"lifeops_test_{uuid.uuid4().hex}"
    created_database_url = await _create_database(database_name)
    try:
        yield created_database_url
    finally:
        await close_database_engine()
        await _drop_database(database_name)


@pytest_asyncio.fixture
async def alembic_env(database_url: str) -> dict[str, str]:
    env = os.environ.copy()
    env["APP_ENV"] = "test"
    env["APP_BASE_URL"] = "http://testserver"
    env["JWT_SECRET"] = "test-secret"
    env["DATABASE_URL"] = database_url
    return env


@pytest.fixture
def alembic_runner() -> callable:
    def run(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    return run


@pytest_asyncio.fixture
async def migrated_session(
    database_url: str,
    alembic_env: dict[str, str],
) -> AsyncGenerator[AsyncSession, None]:
    upgrade_process = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env=alembic_env,
        capture_output=True,
        text=True,
        check=False,
    )
    if upgrade_process.returncode != 0:
        pytest.fail(upgrade_process.stderr or upgrade_process.stdout)

    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)

    async with session_factory() as session:
        yield session

    await engine.dispose()
