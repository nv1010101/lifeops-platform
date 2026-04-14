from __future__ import annotations

import pytest

from app.memberships.dependencies import is_role_sufficient
from app.memberships.models import MembershipRole


@pytest.mark.parametrize(
    ("current_role", "required_role", "expected"),
    [
        (MembershipRole.ADMIN, MembershipRole.ADMIN, True),
        (MembershipRole.ADMIN, MembershipRole.MEMBER, True),
        (MembershipRole.ADMIN, MembershipRole.VIEWER, True),
        (MembershipRole.MEMBER, MembershipRole.ADMIN, False),
        (MembershipRole.MEMBER, MembershipRole.MEMBER, True),
        (MembershipRole.MEMBER, MembershipRole.VIEWER, True),
        (MembershipRole.VIEWER, MembershipRole.ADMIN, False),
        (MembershipRole.VIEWER, MembershipRole.MEMBER, False),
        (MembershipRole.VIEWER, MembershipRole.VIEWER, True),
        ("admin", "member", True),
        ("viewer", "admin", False),
    ],
)
def test_is_role_sufficient_matrix(
    current_role: MembershipRole,
    required_role: MembershipRole,
    expected: bool,
) -> None:
    assert is_role_sufficient(current_role, required_role) is expected
