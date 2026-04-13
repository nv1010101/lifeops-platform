"""slice 03 baseline schema

Revision ID: 20260413_0001
Revises:
Create Date: 2026-04-13 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260413_0001"
down_revision = None
branch_labels = None
depends_on = None


space_type_enum = postgresql.ENUM("personal", "shared", name="space_type", create_type=False)
membership_role_enum = postgresql.ENUM(
    "admin",
    "member",
    "viewer",
    name="membership_role",
    create_type=False,
)
module_health_status_enum = postgresql.ENUM(
    "healthy",
    "unavailable",
    name="module_health_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    space_type_enum.create(bind, checkfirst=True)
    membership_role_enum.create(bind, checkfirst=True)
    module_health_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("hashed_password", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )

    op.create_table(
        "modules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("module_id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("api_version", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_modules")),
        sa.UniqueConstraint("module_id", name=op.f("uq_modules_module_id")),
    )

    op.create_table(
        "spaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", space_type_enum, nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name=op.f("fk_spaces_owner_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_spaces")),
    )
    op.create_index(op.f("ix_spaces_owner_id"), "spaces", ["owner_id"], unique=False)

    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("space_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", membership_role_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], name=op.f("fk_memberships_space_id_spaces")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_memberships_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memberships")),
        sa.UniqueConstraint("user_id", "space_id", name=op.f("uq_memberships_user_id_space_id")),
    )
    op.create_index(op.f("ix_memberships_space_id"), "memberships", ["space_id"], unique=False)

    op.create_table(
        "module_health",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("module_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", module_health_status_enum, nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"], name=op.f("fk_module_health_module_id_modules")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_module_health")),
        sa.UniqueConstraint("module_id", name=op.f("uq_module_health_module_id")),
    )

    op.create_table(
        "module_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("module_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("internal_bearer_token", sa.Text(), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), server_default=sa.text("10"), nullable=False),
        sa.CheckConstraint("timeout_seconds > 0", name=op.f("ck_module_config_timeout_seconds_positive")),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"], name=op.f("fk_module_config_module_id_modules")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_module_config")),
        sa.UniqueConstraint("module_id", name=op.f("uq_module_config_module_id")),
    )

    op.create_table(
        "platform_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("space_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("is_read", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["space_id"],
            ["spaces.id"],
            name=op.f("fk_platform_notifications_space_id_spaces"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_platform_notifications_user_id_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_platform_notifications")),
    )
    op.create_index(
        op.f("ix_platform_notifications_user_id_created_at"),
        "platform_notifications",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_platform_notifications_space_id"),
        "platform_notifications",
        ["space_id"],
        unique=False,
    )

    op.create_table(
        "dashboard_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("space_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.CheckConstraint(
            "config IS NULL OR jsonb_typeof(config) = 'object'",
            name=op.f("ck_dashboard_preferences_config_object"),
        ),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], name=op.f("fk_dashboard_preferences_space_id_spaces")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_dashboard_preferences_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dashboard_preferences")),
        sa.UniqueConstraint("user_id", "space_id", name=op.f("uq_dashboard_preferences_user_id_space_id")),
    )
    op.create_index(
        op.f("ix_dashboard_preferences_space_id"),
        "dashboard_preferences",
        ["space_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_dashboard_preferences_space_id"), table_name="dashboard_preferences")
    op.drop_table("dashboard_preferences")

    op.drop_index(op.f("ix_platform_notifications_space_id"), table_name="platform_notifications")
    op.drop_index(
        op.f("ix_platform_notifications_user_id_created_at"),
        table_name="platform_notifications",
    )
    op.drop_table("platform_notifications")

    op.drop_table("module_config")
    op.drop_table("module_health")

    op.drop_index(op.f("ix_memberships_space_id"), table_name="memberships")
    op.drop_table("memberships")

    op.drop_index(op.f("ix_spaces_owner_id"), table_name="spaces")
    op.drop_table("spaces")

    op.drop_table("modules")
    op.drop_table("users")

    bind = op.get_bind()
    module_health_status_enum.drop(bind, checkfirst=True)
    membership_role_enum.drop(bind, checkfirst=True)
    space_type_enum.drop(bind, checkfirst=True)
