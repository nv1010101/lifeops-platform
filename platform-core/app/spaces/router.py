from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import select

from app.auth.dependencies import CurrentUserDependency
from app.dependencies import DatabaseSessionDependency
from app.memberships.models import Membership, MembershipRole
from app.spaces.models import Space, SpaceType
from app.spaces.schemas import (
    CreateSpaceRequest,
    CreateSpaceResponse,
    SpaceListItem,
    SpaceListResponse,
    SpacePayload,
)

router = APIRouter(prefix="/spaces", tags=["spaces"])


@router.post("", response_model=CreateSpaceResponse, status_code=status.HTTP_201_CREATED)
async def create_shared_space(
    payload: CreateSpaceRequest,
    current_user: CurrentUserDependency,
    db: DatabaseSessionDependency,
) -> CreateSpaceResponse:
    space = Space(
        name=payload.name,
        type=SpaceType.SHARED,
        owner_id=current_user.id,
    )
    db.add(space)
    await db.flush()

    db.add(
        Membership(
            user_id=current_user.id,
            space_id=space.id,
            role=MembershipRole.ADMIN,
        )
    )
    await db.commit()

    return CreateSpaceResponse(
        data=SpacePayload(
            space_id=str(space.id),
            name=space.name,
            type=space.type.value,
        )
    )


@router.get("", response_model=SpaceListResponse)
async def list_spaces_for_current_user(
    current_user: CurrentUserDependency,
    db: DatabaseSessionDependency,
) -> SpaceListResponse:
    rows = (
        await db.execute(
            select(Space, Membership.role)
            .join(Membership, Membership.space_id == Space.id)
            .where(Membership.user_id == current_user.id)
            .order_by(Space.created_at.asc(), Space.id.asc())
        )
    ).all()

    items = [
        SpaceListItem(
            space_id=str(space.id),
            name=space.name,
            type=space.type.value,
            role=role.value,
        )
        for space, role in rows
    ]
    return SpaceListResponse(items=items, total=len(items))
