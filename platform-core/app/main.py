from __future__ import annotations

from fastapi import FastAPI

from app.config import Settings, get_settings
from app.errors import register_exception_handlers
from app.middleware.context import register_request_context_middleware
from app.routers.health import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        docs_url="/docs" if resolved_settings.app_env != "production" else None,
        redoc_url=None,
    )
    app.state.settings = resolved_settings
    register_request_context_middleware(app)
    register_exception_handlers(app)
    app.include_router(health_router)
    return app
