from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.registry.models import ModuleConfig, ModuleHealth, ModuleHealthStatus, PlatformModule
from app.registry.types import RegistryModuleConfig, RegistryModuleListItem


class RegistryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_module_registration(self, config: RegistryModuleConfig) -> None:
        module_insert = insert(PlatformModule).values(
            module_id=config.module_id,
            display_name=config.display_name,
            base_url=config.base_url,
            api_version=config.api_version,
            is_active=config.is_active,
        )
        module_upsert = module_insert.on_conflict_do_update(
            index_elements=[PlatformModule.module_id],
            set_={
                "display_name": module_insert.excluded.display_name,
                "base_url": module_insert.excluded.base_url,
                "api_version": module_insert.excluded.api_version,
                "is_active": module_insert.excluded.is_active,
                "updated_at": func.now(),
            },
        ).returning(PlatformModule.id)
        module_row_id = (await self.session.execute(module_upsert)).scalar_one()

        module_config_insert = insert(ModuleConfig).values(
            module_id=module_row_id,
            internal_bearer_token=config.internal_bearer_token,
            timeout_seconds=config.timeout_seconds,
        )
        module_config_upsert = module_config_insert.on_conflict_do_update(
            index_elements=[ModuleConfig.module_id],
            set_={
                "internal_bearer_token": module_config_insert.excluded.internal_bearer_token,
                "timeout_seconds": module_config_insert.excluded.timeout_seconds,
            },
        )
        await self.session.execute(module_config_upsert)

        module_health_insert = insert(ModuleHealth).values(
            module_id=module_row_id,
            status=ModuleHealthStatus.UNAVAILABLE,
        )
        module_health_upsert = module_health_insert.on_conflict_do_nothing(
            index_elements=[ModuleHealth.module_id]
        )
        await self.session.execute(module_health_upsert)

    async def deactivate_modules_not_in_config(self, configured_module_ids: Sequence[str]) -> None:
        statement = (
            update(PlatformModule)
            .where(PlatformModule.is_active.is_(True))
            .values(is_active=False, updated_at=func.now())
        )
        if configured_module_ids:
            statement = statement.where(PlatformModule.module_id.not_in(configured_module_ids))
        await self.session.execute(statement)

    async def list_modules(self) -> list[RegistryModuleListItem]:
        rows = (
            await self.session.execute(
                select(
                    PlatformModule.module_id,
                    PlatformModule.display_name,
                    PlatformModule.api_version,
                    ModuleHealth.status,
                )
                .select_from(PlatformModule)
                .outerjoin(ModuleHealth, ModuleHealth.module_id == PlatformModule.id)
                .where(PlatformModule.is_active.is_(True))
                .order_by(PlatformModule.display_name.asc(), PlatformModule.module_id.asc())
            )
        ).all()

        return [
            RegistryModuleListItem(
                module_id=module_id,
                display_name=display_name,
                api_version=api_version,
                status=status or ModuleHealthStatus.UNAVAILABLE,
            )
            for module_id, display_name, api_version, status in rows
        ]
