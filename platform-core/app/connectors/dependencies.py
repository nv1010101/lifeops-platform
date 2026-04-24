from __future__ import annotations

from collections.abc import Callable

from app.connectors.base import ModuleConnector
from app.connectors.resolver import get_connector
from app.dependencies import DatabaseSessionDependency


def get_module_connector(module_id: str) -> Callable[..., ModuleConnector]:
    async def dependency(db: DatabaseSessionDependency) -> ModuleConnector:
        return await get_connector(module_id, db)

    return dependency
