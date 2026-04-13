from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.auth.service import SESSION_COOKIE_NAME, SESSION_COOKIE_PATH, SESSION_COOKIE_SAMESITE
from app.middleware.context import attach_context_headers, get_request_context_from_request

logger = logging.getLogger(__name__)

ERROR_CODES_BY_STATUS: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: "payload_too_large",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "validation_error",
    status.HTTP_429_TOO_MANY_REQUESTS: "rate_limited",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "internal_error",
    status.HTTP_502_BAD_GATEWAY: "module_error",
    status.HTTP_503_SERVICE_UNAVAILABLE: "module_unavailable",
    status.HTTP_504_GATEWAY_TIMEOUT: "module_timeout",
}

DEFAULT_MESSAGES_BY_STATUS: dict[int, str] = {
    status.HTTP_400_BAD_REQUEST: "Bad request.",
    status.HTTP_401_UNAUTHORIZED: "Authentication required.",
    status.HTTP_403_FORBIDDEN: "Access denied.",
    status.HTTP_404_NOT_FOUND: "Resource not found.",
    status.HTTP_409_CONFLICT: "Request conflict.",
    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: "Request payload is too large.",
    status.HTTP_422_UNPROCESSABLE_ENTITY: "Request validation failed.",
    status.HTTP_429_TOO_MANY_REQUESTS: "Too many requests.",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "Internal server error.",
    status.HTTP_502_BAD_GATEWAY: "Module returned an invalid response.",
    status.HTTP_503_SERVICE_UNAVAILABLE: "Module is unavailable.",
    status.HTTP_504_GATEWAY_TIMEOUT: "Module request timed out.",
}


class ApplicationHTTPException(StarletteHTTPException):
    def __init__(
        self,
        status_code: int,
        detail: str | None = None,
        *,
        clear_session_cookie: bool = False,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.clear_session_cookie = clear_session_cookie


def _get_error_code(status_code: int) -> str:
    return ERROR_CODES_BY_STATUS.get(status_code, "http_error")


def _get_default_message(status_code: int) -> str:
    return DEFAULT_MESSAGES_BY_STATUS.get(status_code, "Request failed.")


def _extract_http_exception_message(exc: StarletteHTTPException) -> str:
    if isinstance(exc.detail, str) and exc.detail.strip():
        return exc.detail
    return _get_default_message(exc.status_code)


def _sanitize_validation_details(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sanitize_value(value: Any) -> Any:
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, list):
            return [sanitize_value(item) for item in value]
        if isinstance(value, tuple):
            return [sanitize_value(item) for item in value]
        if isinstance(value, dict):
            return {key: sanitize_value(item) for key, item in value.items()}
        return str(value)

    sanitized_errors: list[dict[str, Any]] = []

    for error in errors:
        sanitized_errors.append(
            {
                key: sanitize_value(value)
                for key, value in error.items()
                if key != "input"
            }
        )

    return sanitized_errors


def build_error_response(
    request: Request,
    status_code: int,
    *,
    code: str | None = None,
    message: str | None = None,
    details: Any = None,
) -> JSONResponse:
    request_context = get_request_context_from_request(request)
    payload = {
        "error": {
            "code": code or _get_error_code(status_code),
            "message": message or _get_default_message(status_code),
            "request_id": request_context.request_id,
            "correlation_id": request_context.correlation_id,
            "details": details,
        }
    }

    response = JSONResponse(status_code=status_code, content=payload)
    attach_context_headers(response, request_context)
    return response


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return build_error_response(
            request,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="Request validation failed.",
            details=_sanitize_validation_details(exc.errors()),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        response = build_error_response(
            request,
            exc.status_code,
            message=_extract_http_exception_message(exc),
        )
        if isinstance(exc, ApplicationHTTPException) and exc.clear_session_cookie:
            response.delete_cookie(
                key=SESSION_COOKIE_NAME,
                path=SESSION_COOKIE_PATH,
                httponly=True,
                samesite=SESSION_COOKIE_SAMESITE,
                secure=True,
            )
        return response

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception("Unhandled application exception")
        return build_error_response(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="Internal server error.",
        )
