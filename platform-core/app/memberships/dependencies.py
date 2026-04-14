from __future__ import annotations

from collections.abc import Callable

from fastapi import status

from app.errors import ApplicationHTTPException
from app.memberships.models import Membership, MembershipRole
from app.spaces.dependencies import CurrentSpaceDependency

ROLE_PRIORITY: dict[MembershipRole, int] = {
    MembershipRole.VIEWER: 1,
    MembershipRole.MEMBER: 2,
    MembershipRole.ADMIN: 3,
}


def resolve_membership_role(role: MembershipRole | str) -> MembershipRole:
    if isinstance(role, MembershipRole):
        return role
    return MembershipRole(role)


def is_role_sufficient(current_role: MembershipRole | str, required_role: MembershipRole | str) -> bool:
    resolved_current_role = resolve_membership_role(current_role)
    resolved_required_role = resolve_membership_role(required_role)
    return ROLE_PRIORITY[resolved_current_role] >= ROLE_PRIORITY[resolved_required_role]


def require_role(required_role: MembershipRole | str) -> Callable[..., Membership]:
    resolved_required_role = resolve_membership_role(required_role)

    async def dependency(current_space: CurrentSpaceDependency) -> Membership:
        _, membership = current_space
        if not is_role_sufficient(membership.role, resolved_required_role):
            raise ApplicationHTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role for this action.",
                code="forbidden",
            )
        return membership

    return dependency
