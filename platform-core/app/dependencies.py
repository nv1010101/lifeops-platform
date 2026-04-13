from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.config import Settings
from app.middleware.context import RequestContext, get_request_context_from_request


def get_settings_dependency(request: Request) -> Settings:
    return request.app.state.settings


def get_request_context_dependency(request: Request) -> RequestContext:
    return get_request_context_from_request(request)


SettingsDependency = Annotated[Settings, Depends(get_settings_dependency)]
RequestContextDependency = Annotated[RequestContext, Depends(get_request_context_dependency)]
