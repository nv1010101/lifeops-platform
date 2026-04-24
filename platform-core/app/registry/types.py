from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.registry.models import ModuleHealthStatus

DEFAULT_MODULE_TIMEOUT_SECONDS: Final[int] = 10


@dataclass(frozen=True, slots=True)
class RegistryModuleConfig:
    module_id: str
    display_name: str
    base_url: str
    api_version: str
    internal_bearer_token: str
    is_active: bool = True
    timeout_seconds: int = DEFAULT_MODULE_TIMEOUT_SECONDS


@dataclass(frozen=True, slots=True)
class RegistryModuleListItem:
    module_id: str
    display_name: str
    api_version: str
    status: ModuleHealthStatus


@dataclass(frozen=True, slots=True)
class RegistryModuleRuntime:
    module_id: str
    base_url: str
    internal_bearer_token: str
    timeout_seconds: int
    status: ModuleHealthStatus
