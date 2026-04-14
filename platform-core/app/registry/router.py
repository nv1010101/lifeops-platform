from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import DatabaseSessionDependency
from app.registry.repository import RegistryRepository
from app.registry.schemas import RegistryModuleItem, RegistryModuleListResponse

router = APIRouter(prefix="/registry", tags=["registry"])


@router.get("/modules", response_model=RegistryModuleListResponse)
async def list_registry_modules(db: DatabaseSessionDependency) -> RegistryModuleListResponse:
    repository = RegistryRepository(db)
    modules = await repository.list_modules()

    items = [
        RegistryModuleItem(
            module_id=module.module_id,
            display_name=module.display_name,
            api_version=module.api_version,
            status=module.status,
        )
        for module in modules
    ]
    return RegistryModuleListResponse(items=items, total=len(items))
