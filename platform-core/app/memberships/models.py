from __future__ import annotations

import enum
from datetime import datetime
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UUIDPrimaryKeyMixin


class MembershipRole(str, enum.Enum):
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


MEMBERSHIP_ROLE_ENUM = Enum(
    MembershipRole,
    name="membership_role",
    values_callable=lambda members: [member.value for member in members],
)


class Membership(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "space_id", name="uq_memberships_user_id_space_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    space_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("spaces.id"),
        nullable=False,
        index=True,
    )
    role: Mapped[MembershipRole] = mapped_column(
        MEMBERSHIP_ROLE_ENUM,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user = relationship("User", back_populates="memberships")
    space = relationship("Space", back_populates="memberships")
