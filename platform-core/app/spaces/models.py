from __future__ import annotations

import enum
from datetime import datetime
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UUIDPrimaryKeyMixin


class SpaceType(str, enum.Enum):
    PERSONAL = "personal"
    SHARED = "shared"


SPACE_TYPE_ENUM = Enum(
    SpaceType,
    name="space_type",
    values_callable=lambda members: [member.value for member in members],
)


class Space(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "spaces"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[SpaceType] = mapped_column(
        SPACE_TYPE_ENUM,
        nullable=False,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner = relationship("User", back_populates="owned_spaces")
    memberships = relationship("Membership", back_populates="space")
    notifications = relationship("PlatformNotification", back_populates="space")
    dashboard_preferences = relationship("DashboardPreference", back_populates="space")
