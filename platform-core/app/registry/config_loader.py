from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from json import JSONDecodeError
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.registry.repository import RegistryRepository
from app.registry.types import RegistryModuleConfig

logger = logging.getLogger(__name__)

MODULE_ID_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class _ModuleConfigInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    module_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    api_version: str = Field(min_length=1)
    internal_bearer_token: str = Field(min_length=1)
    is_active: bool = True
    timeout_seconds: int = Field(default=10, gt=0)

    @field_validator("module_id")
    @classmethod
    def validate_module_id_slug(cls, value: str) -> str:
        normalized = value.strip()
        if not MODULE_ID_SLUG_PATTERN.fullmatch(normalized):
            raise ValueError("module_id must be a lowercase slug.")
        return normalized

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name must not be empty.")
        return normalized

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute http(s) URL.")
        return normalized

    @field_validator("api_version", "internal_bearer_token")
    @classmethod
    def validate_non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be empty.")
        return normalized


def load_configured_modules(settings: Settings) -> list[RegistryModuleConfig]:
    return parse_modules_config(settings.modules_config)


def load_configured_modules_for_startup(
    settings: Settings,
) -> tuple[list[RegistryModuleConfig], bool]:
    return _parse_modules_config(settings.modules_config)


def parse_modules_config(modules_config_raw: str | None) -> list[RegistryModuleConfig]:
    configured_modules, _ = _parse_modules_config(modules_config_raw)
    return configured_modules


def _parse_modules_config(
    modules_config_raw: str | None,
) -> tuple[list[RegistryModuleConfig], bool]:
    if modules_config_raw is None or not modules_config_raw.strip():
        return [], True

    try:
        parsed_payload = json.loads(modules_config_raw)
    except JSONDecodeError:
        logger.warning("MODULES_CONFIG contains invalid JSON and will be ignored.")
        return [], False

    if not isinstance(parsed_payload, list):
        logger.warning(
            "MODULES_CONFIG must be a JSON array; got %s.",
            type(parsed_payload).__name__,
        )
        return [], False

    return _parse_module_entries(parsed_payload), True


def _parse_module_entries(parsed_payload: Sequence[object]) -> list[RegistryModuleConfig]:
    result: list[RegistryModuleConfig] = []

    for index, raw_entry in enumerate(parsed_payload):
        if not isinstance(raw_entry, dict):
            logger.warning(
                "Skipping module declaration at index %s because it is not an object.",
                index,
            )
            continue

        try:
            validated_entry = _ModuleConfigInput.model_validate(raw_entry)
        except ValidationError as exc:
            invalid_fields = sorted(
                {".".join(str(part) for part in err["loc"]) for err in exc.errors()}
            )
            logger.warning(
                "Skipping module declaration at index %s due to invalid fields: %s",
                index,
                ", ".join(invalid_fields) if invalid_fields else "unknown",
            )
            continue

        result.append(
            RegistryModuleConfig(
                module_id=validated_entry.module_id,
                display_name=validated_entry.display_name,
                base_url=validated_entry.base_url,
                api_version=validated_entry.api_version,
                internal_bearer_token=validated_entry.internal_bearer_token,
                is_active=validated_entry.is_active,
                timeout_seconds=validated_entry.timeout_seconds,
            )
        )

    return result


async def seed_registry_from_config(
    session: AsyncSession,
    configured_modules: Sequence[RegistryModuleConfig],
) -> None:
    repository = RegistryRepository(session)
    for config in configured_modules:
        await repository.upsert_module_registration(config)

    configured_module_ids = [config.module_id for config in configured_modules]
    await repository.deactivate_modules_not_in_config(configured_module_ids)
    await session.commit()
