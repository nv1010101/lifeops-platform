from __future__ import annotations

import json
from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.registry.config_loader import parse_modules_config, seed_registry_from_config
from app.registry.models import ModuleConfig, ModuleHealth, ModuleHealthStatus, PlatformModule

MODULES_CONFIG_PAYLOAD = json.dumps(
    [
        {
            "module_id": "vocabulary",
            "display_name": "Vocabulary",
            "base_url": "http://vocabulary-service:8001",
            "api_version": "1",
            "internal_bearer_token": "token-vocabulary",
        }
    ]
)


# Overrides conftest.db_settings to inject MODULES_CONFIG.
@pytest_asyncio.fixture
async def db_settings(database_url: str) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        app_base_url="http://testserver",
        database_url=database_url,
        session_secret="test-session-secret",
        modules_config=MODULES_CONFIG_PAYLOAD,
    )


@pytest_asyncio.fixture
async def raw_session(
    db_client,
    database_url: str,
) -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def test_registry_modules_endpoint_returns_seeded_modules_with_unavailable_status(
    db_client,
) -> None:
    response = db_client.get("/registry/modules")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "module_id": "vocabulary",
                "display_name": "Vocabulary",
                "api_version": "1",
                "status": "unavailable",
            }
        ],
        "total": 1,
    }


async def test_registry_module_listing_does_not_expose_internal_module_config(
    db_client,
    raw_session,
) -> None:
    response = db_client.get("/registry/modules")
    payload = response.json()

    module = (
        await raw_session.execute(
            select(PlatformModule).where(PlatformModule.module_id == "vocabulary")
        )
    ).scalar_one()
    module_health = (
        await raw_session.execute(
            select(ModuleHealth).where(ModuleHealth.module_id == module.id)
        )
    ).scalar_one()
    module_config = (
        await raw_session.execute(
            select(ModuleConfig).where(ModuleConfig.module_id == module.id)
        )
    ).scalar_one()

    assert module_health.status is ModuleHealthStatus.UNAVAILABLE
    assert module_config.internal_bearer_token == "token-vocabulary"

    listed_item = payload["items"][0]
    assert "base_url" not in listed_item
    assert "internal_bearer_token" not in listed_item


async def test_registry_seeding_is_idempotent_after_repeated_seed_call(
    db_client,
    raw_session,
) -> None:
    configured_modules = parse_modules_config(MODULES_CONFIG_PAYLOAD)
    await seed_registry_from_config(raw_session, configured_modules)

    module_count = (
        await raw_session.execute(
            select(func.count()).select_from(PlatformModule).where(
                PlatformModule.module_id == "vocabulary"
            )
        )
    ).scalar_one()
    module_config_count = (
        await raw_session.execute(
            select(func.count()).select_from(ModuleConfig).where(
                ModuleConfig.module_id
                == select(PlatformModule.id)
                .where(PlatformModule.module_id == "vocabulary")
                .scalar_subquery()
            )
        )
    ).scalar_one()
    module_health_count = (
        await raw_session.execute(
            select(func.count()).select_from(ModuleHealth).where(
                ModuleHealth.module_id
                == select(PlatformModule.id)
                .where(PlatformModule.module_id == "vocabulary")
                .scalar_subquery()
            )
        )
    ).scalar_one()

    assert module_count == 1
    assert module_config_count == 1
    assert module_health_count == 1


async def test_registry_seeding_with_empty_config_deactivates_all_modules(
    db_client,
    raw_session,
) -> None:
    await seed_registry_from_config(raw_session, [])

    response = db_client.get("/registry/modules")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}

    module_rows = (await raw_session.execute(select(PlatformModule))).scalars().all()
    assert len(module_rows) == 1
    assert module_rows[0].module_id == "vocabulary"
    assert module_rows[0].is_active is False
