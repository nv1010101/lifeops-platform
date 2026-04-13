from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UUIDPrimaryKeyMixin


class ModuleHealthStatus(str, enum.Enum):
    HEALTHY = "healthy"
    UNAVAILABLE = "unavailable"


MODULE_HEALTH_STATUS_ENUM = Enum(
    ModuleHealthStatus,
    name="module_health_status",
    values_callable=lambda members: [member.value for member in members],
)


class PlatformModule(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "modules"

    module_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    api_version: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
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

    health = relationship("ModuleHealth", back_populates="module", uselist=False)
    config = relationship("ModuleConfig", back_populates="module", uselist=False)


class ModuleHealth(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "module_health"

    module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("modules.id"),
        nullable=False,
        unique=True,
    )
    status: Mapped[ModuleHealthStatus] = mapped_column(
        MODULE_HEALTH_STATUS_ENUM,
        nullable=False,
    )
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    module = relationship("PlatformModule", back_populates="health")


class ModuleConfig(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "module_config"
    __table_args__ = (CheckConstraint("timeout_seconds > 0", name="timeout_seconds_positive"),)

    module_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("modules.id"),
        nullable=False,
        unique=True,
    )
    internal_bearer_token: Mapped[str] = mapped_column(Text, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
        server_default=text("10"),
    )

    module = relationship("PlatformModule", back_populates="config")

    def __repr__(self) -> str:
        return (
            f"ModuleConfig(id={self.id!s}, module_id={self.module_id!s}, "
            f"timeout_seconds={self.timeout_seconds!r}, internal_bearer_token='***')"
        )
