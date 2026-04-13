from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import uuid4

from fastapi import FastAPI, Request, Response

_request_context_var: ContextVar["RequestContext | None"] = ContextVar(
    "request_context",
    default=None,
)


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    correlation_id: str


def _resolve_header_value(value: str | None) -> str:
    if value and value.strip():
        return value.strip()
    return str(uuid4())


def create_request_context(request: Request) -> RequestContext:
    return RequestContext(
        request_id=_resolve_header_value(request.headers.get("X-Request-Id")),
        correlation_id=_resolve_header_value(request.headers.get("X-Correlation-Id")),
    )


def current_request_context() -> RequestContext | None:
    return _request_context_var.get()


def get_request_context_from_request(request: Request) -> RequestContext:
    request_context = getattr(request.state, "request_context", None)
    if request_context is not None:
        return request_context

    request_context = current_request_context()
    if request_context is not None:
        request.state.request_context = request_context
        return request_context

    request_context = RequestContext(request_id=str(uuid4()), correlation_id=str(uuid4()))
    request.state.request_context = request_context
    return request_context


def attach_context_headers(response: Response, request_context: RequestContext) -> None:
    response.headers["X-Request-Id"] = request_context.request_id
    response.headers["X-Correlation-Id"] = request_context.correlation_id


def register_request_context_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_context = create_request_context(request)
        request.state.request_context = request_context
        token = _request_context_var.set(request_context)

        try:
            response = await call_next(request)
            attach_context_headers(response, request_context)
            return response
        finally:
            _request_context_var.reset(token)
