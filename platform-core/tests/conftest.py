from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi import APIRouter, HTTPException, Query
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.dependencies import RequestContextDependency
from app.main import create_app


def build_test_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        app_base_url="http://testserver",
        database_url="postgresql://lifeops:lifeops@localhost:5432/lifeops_test",
        jwt_secret="test-secret",
    )


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Generator[None, None, None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    return build_test_settings()


@pytest.fixture
def client(settings: Settings) -> Generator[TestClient, None, None]:
    app = create_app(settings=settings)
    router = APIRouter()

    @router.get("/test/context")
    def read_request_context(request_context: RequestContextDependency) -> dict[str, str]:
        return {
            "request_id": request_context.request_id,
            "correlation_id": request_context.correlation_id,
        }

    @router.get("/test/http/{status_code}")
    def raise_http_error(status_code: int) -> None:
        detail_by_status = {
            400: "Bad input for test route.",
            404: "Missing test resource.",
        }
        raise HTTPException(
            status_code=status_code,
            detail=detail_by_status.get(status_code, "HTTP test error."),
        )

    @router.get("/test/validation")
    def validation_route(limit: int = Query(ge=1)) -> dict[str, int]:
        return {"limit": limit}

    @router.get("/test/crash")
    def crash_route() -> None:
        raise RuntimeError("boom")

    app.include_router(router)

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
