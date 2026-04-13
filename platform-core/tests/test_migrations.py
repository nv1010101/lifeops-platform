from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


REQUIRED_TABLES = {
    "alembic_version",
    "dashboard_preferences",
    "memberships",
    "module_config",
    "module_health",
    "modules",
    "platform_notifications",
    "spaces",
    "users",
}


def test_alembic_upgrade_head_applies_cleanly_on_fresh_database(alembic_runner, alembic_env, database_url) -> None:
    first_upgrade = alembic_runner("upgrade", "head", env=alembic_env)
    assert first_upgrade.returncode == 0, first_upgrade.stderr or first_upgrade.stdout

    second_upgrade = alembic_runner("upgrade", "head", env=alembic_env)
    assert second_upgrade.returncode == 0, second_upgrade.stderr or second_upgrade.stdout


def test_alembic_downgrade_and_reupgrade_succeeds(alembic_runner, alembic_env) -> None:
    upgrade = alembic_runner("upgrade", "head", env=alembic_env)
    assert upgrade.returncode == 0, upgrade.stderr or upgrade.stdout

    downgrade = alembic_runner("downgrade", "-1", env=alembic_env)
    assert downgrade.returncode == 0, downgrade.stderr or downgrade.stdout

    reupgrade = alembic_runner("upgrade", "head", env=alembic_env)
    assert reupgrade.returncode == 0, reupgrade.stderr or reupgrade.stdout


async def test_required_tables_exist_after_upgrade(alembic_runner, alembic_env, database_url) -> None:
    upgrade = alembic_runner("upgrade", "head", env=alembic_env)
    assert upgrade.returncode == 0, upgrade.stderr or upgrade.stdout

    engine = create_async_engine(database_url, pool_pre_ping=True)

    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = 'public'
                    """
                )
            )
            table_names = {row[0] for row in result}
    finally:
        await engine.dispose()

    assert REQUIRED_TABLES.issubset(table_names)
