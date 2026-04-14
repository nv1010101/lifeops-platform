from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID, uuid4

import httpx
from fastapi import status

from app.connectors.base import ModuleConnector
from app.connectors.circuit_breaker import ModuleCircuitBreaker
from app.errors import ApplicationHTTPException
from app.registry.models import ModuleHealthStatus
from app.registry.types import DEFAULT_MODULE_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class HTTPModuleConnector(ModuleConnector):
    def __init__(
        self,
        *,
        module_id: str,
        base_url: str,
        internal_bearer_token: str,
        timeout_seconds: int = DEFAULT_MODULE_TIMEOUT_SECONDS,
        module_status: ModuleHealthStatus = ModuleHealthStatus.HEALTHY,
        circuit_breaker: ModuleCircuitBreaker,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._module_id = module_id
        self._base_url = base_url.rstrip("/")
        self._internal_bearer_token = internal_bearer_token
        self._timeout_seconds = timeout_seconds
        self._module_status = module_status
        self._circuit_breaker = circuit_breaker
        self._transport = transport

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
        method_upper = method.upper()
        availability_probe_done = await self._ensure_available()
        headers = self._build_headers(
            method=method_upper,
            user_id=user_id,
            space_id=space_id,
            request_id=request_id,
            correlation_id=correlation_id,
            locale=locale,
            timezone=timezone,
            idempotency_key=idempotency_key,
        )
        decision = await self._circuit_breaker.before_request()
        if not decision.allow_request:
            raise ApplicationHTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Module {self._module_id} is currently unavailable.",
                code="module_unavailable",
            )

        if (
            decision.requires_probe
            and not availability_probe_done
            and not await self._probe_module_health(headers)
        ):
            await self._circuit_breaker.on_probe_failure()
            raise ApplicationHTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Module {self._module_id} is currently unavailable.",
                code="module_unavailable",
            )
        if decision.requires_probe:
            await self._circuit_breaker.on_probe_success()

        try:
            response = await self._send_request(
                method=method_upper,
                path=path,
                headers=headers,
                query_params=query_params,
                body=body,
            )
        except httpx.TimeoutException as exc:
            await self._circuit_breaker.on_failure()
            raise ApplicationHTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"Module {self._module_id} timed out.",
                code="module_timeout",
            ) from exc
        except httpx.TransportError as exc:
            await self._circuit_breaker.on_failure()
            raise ApplicationHTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Module {self._module_id} is unavailable.",
                code="module_unavailable",
            ) from exc

        if response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
            await self._circuit_breaker.on_failure()
            raise ApplicationHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Module {self._module_id} returned a server error.",
                code="module_error",
            )

        if response.status_code >= status.HTTP_400_BAD_REQUEST:
            await self._circuit_breaker.on_success()
            self._raise_client_error(response)

        payload = self._extract_json_object(response)
        if payload is None:
            await self._circuit_breaker.on_failure()
            raise ApplicationHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Module {self._module_id} returned an invalid response.",
                code="module_error",
            )
        await self._circuit_breaker.on_success()
        return payload

    async def _ensure_available(self) -> bool:
        if self._module_status is not ModuleHealthStatus.UNAVAILABLE:
            return False

        health_probe_headers = {"Authorization": f"Bearer {self._internal_bearer_token}"}
        health_check_ok = await self._probe_module_health(health_probe_headers)
        if not health_check_ok:
            raise ApplicationHTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Module {self._module_id} is currently unavailable.",
                code="module_unavailable",
            )
        return True

    def _build_headers(
        self,
        *,
        method: str,
        user_id: UUID,
        space_id: UUID,
        request_id: str,
        correlation_id: str,
        locale: str,
        timezone: str,
        idempotency_key: str | None,
    ) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._internal_bearer_token}",
            "X-User-Id": str(user_id),
            "X-Space-Id": str(space_id),
            "X-Request-Id": request_id,
            "X-Correlation-Id": correlation_id,
            "X-Locale": locale,
            "X-Timezone": timezone,
            "X-Platform-Token": self._build_platform_token(
                user_id=user_id,
                space_id=space_id,
                locale=locale,
                timezone=timezone,
            ),
        }
        if method in WRITE_METHODS:
            headers["X-Idempotency-Key"] = idempotency_key or str(uuid4())
        return headers

    @staticmethod
    def _normalize_path(path: str) -> str:
        if path.startswith("/"):
            return path
        return f"/{path}"

    def _build_platform_token(
        self,
        *,
        user_id: UUID,
        space_id: UUID,
        locale: str,
        timezone: str,
    ) -> str:
        return json.dumps(
            {
                "user_id": str(user_id),
                "space_id": str(space_id),
                "locale": locale,
                "timezone": timezone,
                "audience": self._module_id,
                "issuer": "platform-core",
            },
            separators=(",", ":"),
        )

    async def _send_request(
        self,
        *,
        method: str,
        path: str,
        headers: dict[str, str],
        query_params: dict[str, Any] | None,
        body: dict[str, Any] | None,
    ) -> httpx.Response:
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_seconds,
            transport=self._transport,
        ) as client:
            return await client.request(
                method=method,
                url=self._normalize_path(path),
                headers=headers,
                params=query_params,
                json=body,
            )

    async def _probe_module_health(self, headers: dict[str, str]) -> bool:
        try:
            response = await self._send_request(
                method="GET",
                path="/health",
                headers=headers,
                query_params=None,
                body=None,
            )
        except (httpx.TimeoutException, httpx.TransportError):
            return False

        payload = self._extract_json_object(response)
        if payload is None:
            return False

        return response.status_code == status.HTTP_200_OK and payload.get("status") == "ok"

    def _raise_client_error(self, response: httpx.Response) -> None:
        payload = self._extract_json_object(response)
        error = payload.get("error") if payload else None
        code = error.get("code") if isinstance(error, dict) else None
        message = error.get("message") if isinstance(error, dict) else None

        if isinstance(code, str) and isinstance(message, str) and message.strip():
            raise ApplicationHTTPException(
                status_code=response.status_code,
                detail=message,
                code=code,
            )

        raise ApplicationHTTPException(
            status_code=response.status_code,
            detail=f"Module {self._module_id} returned an invalid error response.",
            code="module_error",
        )

    def _extract_json_object(self, response: httpx.Response) -> dict[str, Any] | None:
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type.lower():
            logger.warning(
                "Module %s returned non-JSON response content_type=%s status=%s",
                self._module_id,
                content_type or "<empty>",
                response.status_code,
            )
            return None

        try:
            payload = response.json()
        except ValueError:
            logger.warning(
                "Module %s returned malformed JSON payload status=%s",
                self._module_id,
                response.status_code,
            )
            return None

        if isinstance(payload, dict):
            return payload
        return None
