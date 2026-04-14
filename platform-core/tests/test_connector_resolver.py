from __future__ import annotations

import pytest
from fastapi import status
from sqlalchemy import insert

from app.connectors.http_connector import HTTPModuleConnector
from app.connectors.resolver import get_connector
from app.errors import ApplicationHTTPException
from app.registry.models import ModuleConfig, ModuleHealthStatus, PlatformModule
from app.registry.repository import RegistryRepository
from app.registry.types import RegistryModuleConfig


async def test_connector_resolver_raises_404_for_unknown_module_id(migrated_session) -> None:
    with pytest.raises(ApplicationHTTPException) as exc_info:
        await get_connector("unknown-module", migrated_session)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.code == "module_not_found"
    assert exc_info.value.detail == "Module unknown-module is not registered."


async def test_connector_resolver_returns_http_connector_for_registered_module(
    migrated_session,
) -> None:
    repository = RegistryRepository(migrated_session)
    await repository.upsert_module_registration(
        RegistryModuleConfig(
            module_id="vocabulary",
            display_name="Vocabulary",
            base_url="http://vocabulary-service:8001",
            api_version="1",
            internal_bearer_token="vocabulary-secret",
            timeout_seconds=9,
        )
    )
    await migrated_session.commit()

    connector = await get_connector("vocabulary", migrated_session)

    assert isinstance(connector, HTTPModuleConnector)


async def test_get_module_runtime_defaults_to_healthy_when_health_row_is_missing(
    migrated_session,
) -> None:
    module_id = (
        await migrated_session.execute(
            insert(PlatformModule)
            .values(
                module_id="notes",
                display_name="Notes",
                base_url="http://notes-service:8002",
                api_version="1",
                is_active=True,
            )
            .returning(PlatformModule.id)
        )
    ).scalar_one()
    await migrated_session.execute(
        insert(ModuleConfig).values(
            module_id=module_id,
            internal_bearer_token="notes-secret",
            timeout_seconds=10,
        )
    )
    await migrated_session.commit()

    repository = RegistryRepository(migrated_session)
    runtime = await repository.get_module_runtime("notes")

    assert runtime is not None
    assert runtime.status is ModuleHealthStatus.HEALTHY
