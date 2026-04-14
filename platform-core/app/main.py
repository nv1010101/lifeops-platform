from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.config import Settings, get_settings
from app.database import AsyncSessionLocal, close_database_engine, get_engine
from app.errors import register_exception_handlers
from app.middleware.context import register_request_context_middleware
from app.model_registry import load_all_models
from app.registry.config_loader import (
    load_configured_modules_for_startup,
    seed_registry_from_config,
)
from app.registry.router import router as registry_router
from app.routers.health import router as health_router
from app.spaces.router import router as spaces_router


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    load_all_models()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        get_engine(resolved_settings)
        configured_modules, config_is_valid = load_configured_modules_for_startup(
            resolved_settings
        )
        if resolved_settings.modules_config is not None and config_is_valid:
            async with AsyncSessionLocal() as session:
                await seed_registry_from_config(session, configured_modules)
        yield
        await close_database_engine()

    app = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        docs_url="/docs" if resolved_settings.app_env != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    register_request_context_middleware(app)
    register_exception_handlers(app)
    app.include_router(auth_router)
    app.include_router(health_router)
    app.include_router(registry_router)
    app.include_router(spaces_router)
    return app
