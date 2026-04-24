from __future__ import annotations

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.base import ModuleConnector
from app.connectors.circuit_breaker import get_module_circuit_breaker
from app.connectors.http_connector import HTTPModuleConnector
from app.errors import ApplicationHTTPException
from app.registry.repository import RegistryRepository


async def get_connector(module_id: str, db: AsyncSession) -> ModuleConnector:
    repository = RegistryRepository(db)
    module_runtime = await repository.get_module_runtime(module_id)
    if module_runtime is None:
        raise ApplicationHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module {module_id} is not registered.",
            code="module_not_found",
        )

    circuit_breaker = await get_module_circuit_breaker(module_runtime.module_id)
    return HTTPModuleConnector(
        module_id=module_runtime.module_id,
        base_url=module_runtime.base_url,
        internal_bearer_token=module_runtime.internal_bearer_token,
        timeout_seconds=module_runtime.timeout_seconds,
        module_status=module_runtime.status,
        circuit_breaker=circuit_breaker,
    )
