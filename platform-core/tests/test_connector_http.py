from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import pytest
from fastapi import status

from app.connectors.circuit_breaker import CircuitState, ModuleCircuitBreaker
from app.connectors.http_connector import HTTPModuleConnector
from app.errors import ApplicationHTTPException
from app.registry.models import ModuleHealthStatus


def _closed_breaker() -> ModuleCircuitBreaker:
    return ModuleCircuitBreaker(initial_state=CircuitState.CLOSED)


def _connector(
    *,
    transport: httpx.AsyncBaseTransport,
    module_status: ModuleHealthStatus = ModuleHealthStatus.HEALTHY,
    token: str = "internal-secret-token",
    timeout_seconds: int = 10,
    base_url: str = "http://module.local",
    circuit_breaker: ModuleCircuitBreaker | None = None,
) -> HTTPModuleConnector:
    return HTTPModuleConnector(
        module_id="vocabulary",
        base_url=base_url,
        internal_bearer_token=token,
        timeout_seconds=timeout_seconds,
        module_status=module_status,
        circuit_breaker=circuit_breaker or _closed_breaker(),
        transport=transport,
    )


def _context() -> dict[str, Any]:
    return {
        "user_id": uuid4(),
        "space_id": uuid4(),
        "request_id": "req-connector-test",
        "correlation_id": "corr-connector-test",
        "locale": "ru-RU",
        "timezone": "Europe/Berlin",
    }


@pytest.mark.asyncio
async def test_connector_forwards_platform_context_headers_on_every_call() -> None:
    context = _context()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/meta"
        assert request.headers["Authorization"] == "Bearer internal-secret-token"
        assert request.headers["X-User-Id"] == str(context["user_id"])
        assert request.headers["X-Space-Id"] == str(context["space_id"])
        assert request.headers["X-Request-Id"] == context["request_id"]
        assert request.headers["X-Correlation-Id"] == context["correlation_id"]
        assert request.headers["X-Locale"] == context["locale"]
        assert request.headers["X-Timezone"] == context["timezone"]
        platform_token = json.loads(request.headers["X-Platform-Token"])
        assert platform_token == {
            "user_id": str(context["user_id"]),
            "space_id": str(context["space_id"]),
            "locale": context["locale"],
            "timezone": context["timezone"],
            "audience": "vocabulary",
            "issuer": "platform-core",
        }
        assert "X-Idempotency-Key" not in request.headers
        return httpx.Response(
            status_code=200,
            headers={"content-type": "application/json"},
            json={"data": {"ok": True}},
        )

    connector = _connector(transport=httpx.MockTransport(handler))
    payload = await connector.call("GET", "/meta", **context)

    assert payload == {"data": {"ok": True}}


@pytest.mark.asyncio
async def test_connector_sets_idempotency_header_for_state_changing_calls() -> None:
    captured_header: str | None = None
    context = _context()

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_header
        captured_header = request.headers.get("X-Idempotency-Key")
        return httpx.Response(
            status_code=200,
            headers={"content-type": "application/json"},
            json={"status": "ok"},
        )

    connector = _connector(transport=httpx.MockTransport(handler))
    await connector.call("POST", "/items", body={"title": "one"}, **context)

    assert captured_header is not None


@pytest.mark.asyncio
async def test_connector_uses_explicit_idempotency_key_when_provided() -> None:
    context = _context()
    explicit_key = "idempotency-explicit-001"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Idempotency-Key"] == explicit_key
        return httpx.Response(
            status_code=200,
            headers={"content-type": "application/json"},
            json={"status": "ok"},
        )

    connector = _connector(transport=httpx.MockTransport(handler))
    await connector.call(
        "PATCH",
        "/items/123",
        body={"title": "updated"},
        idempotency_key=explicit_key,
        **context,
    )


@pytest.mark.asyncio
async def test_internal_bearer_token_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    token = "super-secret-module-token"
    context = _context()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"content-type": "application/json"},
            json={"status": "ok"},
        )

    caplog.set_level(logging.INFO)
    connector = _connector(
        transport=httpx.MockTransport(handler),
        token=token,
    )
    await connector.call("GET", "/health", **context)

    assert token not in caplog.text


@pytest.mark.asyncio
async def test_connector_maps_module_4xx_error_with_original_status() -> None:
    context = _context()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=404,
            headers={"content-type": "application/json"},
            json={"error": {"code": "not_found", "message": "Entity not found in module."}},
        )

    connector = _connector(transport=httpx.MockTransport(handler))
    with pytest.raises(ApplicationHTTPException) as exc_info:
        await connector.call("GET", "/entities/123", **context)

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.code == "not_found"
    assert exc_info.value.detail == "Entity not found in module."


@pytest.mark.asyncio
async def test_connector_maps_module_5xx_error_to_platform_502() -> None:
    context = _context()

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=500,
            headers={"content-type": "application/json"},
            json={"error": {"code": "internal_error", "message": "Module failed."}},
        )

    connector = _connector(transport=httpx.MockTransport(handler))
    with pytest.raises(ApplicationHTTPException) as exc_info:
        await connector.call("POST", "/entities", body={"title": "example"}, **context)

    assert exc_info.value.status_code == status.HTTP_502_BAD_GATEWAY
    assert exc_info.value.code == "module_error"
    assert exc_info.value.detail == "Module vocabulary returned a server error."


@pytest.mark.asyncio
async def test_connector_maps_timeout_errors_to_504_module_timeout() -> None:
    context = _context()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    connector = _connector(transport=httpx.MockTransport(handler))
    with pytest.raises(ApplicationHTTPException) as exc_info:
        await connector.call("GET", "/meta", **context)

    assert exc_info.value.status_code == status.HTTP_504_GATEWAY_TIMEOUT
    assert exc_info.value.code == "module_timeout"
    assert exc_info.value.detail == "Module vocabulary timed out."


@pytest.mark.asyncio
async def test_connector_maps_transport_errors_to_503_module_unavailable() -> None:
    context = _context()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    connector = _connector(transport=httpx.MockTransport(handler))
    with pytest.raises(ApplicationHTTPException) as exc_info:
        await connector.call("GET", "/meta", **context)

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert exc_info.value.code == "module_unavailable"
    assert exc_info.value.detail == "Module vocabulary is unavailable."


@pytest.mark.asyncio
async def test_unavailable_module_rejects_when_health_probe_fails_before_domain_call() -> None:
    context = _context()
    called_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        called_paths.append(request.url.path)
        if request.url.path == "/health":
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(
            status_code=200,
            headers={"content-type": "application/json"},
            json={"status": "ok"},
        )

    connector = _connector(
        transport=httpx.MockTransport(handler),
        module_status=ModuleHealthStatus.UNAVAILABLE,
        circuit_breaker=ModuleCircuitBreaker(initial_state=CircuitState.CLOSED),
    )
    with pytest.raises(ApplicationHTTPException) as exc_info:
        await connector.call("GET", "/meta", **context)

    assert called_paths == ["/health"]
    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert exc_info.value.code == "module_unavailable"
    assert exc_info.value.detail == "Module vocabulary is currently unavailable."


@pytest.mark.asyncio
async def test_unavailable_module_allows_call_after_successful_health_probe() -> None:
    context = _context()
    called_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        called_paths.append(request.url.path)
        if request.url.path == "/health":
            return httpx.Response(
                status_code=200,
                headers={"content-type": "application/json"},
                json={"status": "ok"},
            )
        if request.url.path == "/meta":
            return httpx.Response(
                status_code=200,
                headers={"content-type": "application/json"},
                json={"module_id": "vocabulary"},
            )
        return httpx.Response(
            status_code=404,
            headers={"content-type": "application/json"},
            json={},
        )

    connector = _connector(
        transport=httpx.MockTransport(handler),
        module_status=ModuleHealthStatus.UNAVAILABLE,
        circuit_breaker=ModuleCircuitBreaker(initial_state=CircuitState.CLOSED),
    )
    payload = await connector.call("GET", "/meta", **context)

    assert called_paths == ["/health", "/meta"]
    assert payload == {"module_id": "vocabulary"}


@pytest.mark.asyncio
async def test_half_open_circuit_runs_health_probe_then_domain_call() -> None:
    context = _context()
    called_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        called_paths.append(request.url.path)
        if request.url.path == "/health":
            return httpx.Response(
                status_code=200,
                headers={"content-type": "application/json"},
                json={"status": "ok"},
            )
        return httpx.Response(
            status_code=200,
            headers={"content-type": "application/json"},
            json={"ok": True},
        )

    connector = _connector(
        transport=httpx.MockTransport(handler),
        circuit_breaker=ModuleCircuitBreaker(initial_state=CircuitState.HALF_OPEN),
    )
    payload = await connector.call("GET", "/meta", **context)

    assert called_paths == ["/health", "/meta"]
    assert payload == {"ok": True}


@pytest.fixture
def module_http_server() -> dict[str, Any]:
    captured_calls: list[dict[str, Any]] = []

    class ModuleHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            captured_calls.append(
                {
                    "path": path,
                    "headers": {key: value for key, value in self.headers.items()},
                }
            )

            payload_by_path: dict[str, dict[str, Any]] = {
                "/health": {"status": "ok"},
                "/meta": {
                    "module_id": "vocabulary",
                    "display_name": "Vocabulary",
                    "description": "Vocabulary module",
                    "api_version": "1",
                    "module_version": "0.1.0",
                },
                "/capabilities": {
                    "search": True,
                    "activity": False,
                    "widgets": ["vocabulary_summary"],
                    "views": ["list", "detail"],
                },
            }
            payload = payload_by_path.get(path)
            if payload is None:
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":{"code":"not_found","message":"Unknown route."}}')
                return

            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _: str, *args: Any) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), ModuleHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield {
            "base_url": f"http://127.0.0.1:{server.server_port}",
            "captured_calls": captured_calls,
        }
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.asyncio
async def test_module_contract_endpoints_with_controlled_http_server(
    module_http_server: dict[str, Any],
) -> None:
    context = _context()
    connector = HTTPModuleConnector(
        module_id="vocabulary",
        base_url=module_http_server["base_url"],
        internal_bearer_token="contract-secret-token",
        module_status=ModuleHealthStatus.HEALTHY,
        circuit_breaker=_closed_breaker(),
        timeout_seconds=5,
    )

    health_payload = await connector.call("GET", "/health", **context)
    meta_payload = await connector.call("GET", "/meta", **context)
    capabilities_payload = await connector.call("GET", "/capabilities", **context)

    assert health_payload == {"status": "ok"}
    assert set(meta_payload) >= {
        "module_id",
        "display_name",
        "description",
        "api_version",
        "module_version",
    }
    assert set(capabilities_payload) >= {"search", "activity", "widgets", "views"}

    for captured_call in module_http_server["captured_calls"]:
        headers = captured_call["headers"]
        assert headers["Authorization"] == "Bearer contract-secret-token"
        if captured_call["path"] != "/health":
            assert headers["X-User-Id"] == str(context["user_id"])
            assert headers["X-Space-Id"] == str(context["space_id"])
            assert headers["X-Request-Id"] == context["request_id"]
            assert headers["X-Correlation-Id"] == context["correlation_id"]
            assert headers["X-Locale"] == context["locale"]
            assert headers["X-Timezone"] == context["timezone"]
            assert "X-Platform-Token" in headers
