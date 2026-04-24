from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Request, status
from sqlalchemy import select

from app.auth.dependencies import CurrentUserDependency
from app.dependencies import DatabaseSessionDependency
from app.errors import ApplicationHTTPException
from app.memberships.models import Membership
from app.spaces.models import Space


def _parse_space_id_header(space_id_header: str) -> uuid.UUID:
    try:
        return uuid.UUID(space_id_header)
    except ValueError as exc:
        raise ApplicationHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Space-Id header must be a valid UUID.",
            code="invalid_space_id",
        ) from exc


async def get_current_space(
    request: Request,
    current_user: CurrentUserDependency,
    db: DatabaseSessionDependency,
) -> tuple[Space, Membership]:
    space_id_header = request.headers.get("X-Space-Id")
    if space_id_header is None or not space_id_header.strip():
        raise ApplicationHTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Space-Id header is required.",
            code="missing_space_id",
        )

    space_id = _parse_space_id_header(space_id_header.strip())
    space = await db.get(Space, space_id)
    if space is None:
        raise ApplicationHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Space not found.",
            code="not_found",
        )

    membership = (
        await db.execute(
            select(Membership).where(
                Membership.space_id == space_id,
                Membership.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise ApplicationHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this space.",
            code="forbidden",
        )

    return space, membership


CurrentSpaceDependency = Annotated[tuple[Space, Membership], Depends(get_current_space)]
