from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class ModuleConnector(ABC):
    @abstractmethod
    async def call(
        self,
        method: str,
        path: str,
        *,
        user_id: UUID,
        space_id: UUID,
        request_id: str,
        correlation_id: str,
        locale: str,
        timezone: str,
        body: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Call module API and return normalized JSON payload."""
