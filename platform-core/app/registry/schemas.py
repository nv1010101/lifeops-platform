from __future__ import annotations

from pydantic import BaseModel

from app.registry.models import ModuleHealthStatus


class RegistryModuleItem(BaseModel):
    module_id: str
    display_name: str
    api_version: str
    status: ModuleHealthStatus


class RegistryModuleListResponse(BaseModel):
    items: list[RegistryModuleItem]
    total: int
