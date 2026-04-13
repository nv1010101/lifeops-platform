from __future__ import annotations

from typing import Any, Optional
import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UUIDPrimaryKeyMixin


class DashboardPreference(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "dashboard_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "space_id", name="uq_dashboard_preferences_user_id_space_id"),
        CheckConstraint(
            "config IS NULL OR jsonb_typeof(config) = 'object'",
            name="config_object",
        ),
        Index("ix_dashboard_preferences_space_id", "space_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    space_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id"),
        nullable=False,
    )
    config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    user = relationship("User", back_populates="dashboard_preferences")
    space = relationship("Space", back_populates="dashboard_preferences")
