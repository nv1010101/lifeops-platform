from __future__ import annotations

import uuid

from sqlalchemy import select

from app.auth.service import SESSION_COOKIE_NAME, create_session_token, hash_password
from app.dashboard.models import DashboardPreference
from app.memberships.models import Membership, MembershipRole
from app.spaces.isolation import assert_space_scope
from app.spaces.models import Space, SpaceType
from app.users.models import User


def register_user(db_client, email: str) -> uuid.UUID:
    response = db_client.post(
        "/auth/register",
        json={"email": email, "password": "StrongPassword!42"},
    )
    assert response.status_code == 201
    return uuid.UUID(response.json()["data"]["user_id"])


async def get_personal_space(session, user_id: uuid.UUID) -> Space:
    return (
        await session.execute(
            select(Space).where(
                Space.owner_id == user_id,
                Space.type == SpaceType.PERSONAL,
            )
        )
    ).scalar_one()


async def test_post_spaces_creates_shared_space_and_admin_membership(
    db_client,
    migrated_session,
    db_settings,
) -> None:
    user_id = register_user(db_client, "spaces-owner@example.com")
    db_client.cookies.set(
        SESSION_COOKIE_NAME,
        create_session_token(user_id, settings=db_settings),
    )

    response = db_client.post("/spaces", json={"name": "Family HQ"})

    assert response.status_code == 201
    assert response.json()["data"]["name"] == "Family HQ"
    assert response.json()["data"]["type"] == "shared"
    created_space_id = uuid.UUID(response.json()["data"]["space_id"])

    created_space = await migrated_session.get(Space, created_space_id)
    assert created_space is not None
    assert created_space.owner_id == user_id
    assert created_space.type is SpaceType.SHARED

    created_membership = (
        await migrated_session.execute(
            select(Membership).where(
                Membership.user_id == user_id,
                Membership.space_id == created_space_id,
            )
        )
    ).scalar_one()
    assert created_membership.role is MembershipRole.ADMIN


async def test_get_spaces_returns_only_spaces_where_user_has_membership(
    db_client,
    migrated_session,
    db_settings,
) -> None:
    user_a_id = register_user(db_client, "spaces-user-a@example.com")
    user_b_id = register_user(db_client, "spaces-user-b@example.com")

    user_a_personal_space = await get_personal_space(migrated_session, user_a_id)

    shared_space = Space(
        name="Shared Space",
        type=SpaceType.SHARED,
        owner_id=user_b_id,
    )
    user_b_only_space = Space(
        name="User B Only Space",
        type=SpaceType.SHARED,
        owner_id=user_b_id,
    )
    migrated_session.add_all([shared_space, user_b_only_space])
    await migrated_session.flush()

    migrated_session.add_all(
        [
            Membership(user_id=user_b_id, space_id=shared_space.id, role=MembershipRole.ADMIN),
            Membership(user_id=user_a_id, space_id=shared_space.id, role=MembershipRole.VIEWER),
            Membership(user_id=user_b_id, space_id=user_b_only_space.id, role=MembershipRole.ADMIN),
        ]
    )
    await migrated_session.commit()

    db_client.cookies.set(
        SESSION_COOKIE_NAME,
        create_session_token(user_a_id, settings=db_settings),
    )
    response = db_client.get("/spaces")

    assert response.status_code == 200
    assert response.json()["total"] == 2

    items_by_space_id = {item["space_id"]: item for item in response.json()["items"]}
    assert str(user_a_personal_space.id) in items_by_space_id
    assert str(shared_space.id) in items_by_space_id
    assert str(user_b_only_space.id) not in items_by_space_id
    assert items_by_space_id[str(user_a_personal_space.id)]["role"] == "admin"
    assert items_by_space_id[str(shared_space.id)]["role"] == "viewer"


async def test_get_current_space_without_header_returns_missing_space_id_error(
    db_client,
    db_settings,
) -> None:
    user_id = register_user(db_client, "missing-space-id@example.com")
    db_client.cookies.set(
        SESSION_COOKIE_NAME,
        create_session_token(user_id, settings=db_settings),
    )

    response = db_client.get("/test/current-space")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "missing_space_id"


async def test_get_current_space_with_invalid_space_id_returns_invalid_space_id_error(
    db_client,
    db_settings,
) -> None:
    user_id = register_user(db_client, "invalid-space-id@example.com")
    db_client.cookies.set(
        SESSION_COOKIE_NAME,
        create_session_token(user_id, settings=db_settings),
    )

    response = db_client.get(
        "/test/current-space",
        headers={"X-Space-Id": "not-a-uuid"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_space_id"


async def test_get_current_space_with_missing_space_returns_not_found(
    db_client,
    db_settings,
) -> None:
    user_id = register_user(db_client, "missing-space@example.com")
    db_client.cookies.set(
        SESSION_COOKIE_NAME,
        create_session_token(user_id, settings=db_settings),
    )

    response = db_client.get(
        "/test/current-space",
        headers={"X-Space-Id": str(uuid.uuid4())},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_get_current_space_for_non_member_returns_forbidden(
    db_client,
    migrated_session,
    db_settings,
) -> None:
    user_a_id = register_user(db_client, "non-member-a@example.com")
    user_b_id = register_user(db_client, "non-member-b@example.com")
    user_b_personal_space = await get_personal_space(migrated_session, user_b_id)

    db_client.cookies.set(
        SESSION_COOKIE_NAME,
        create_session_token(user_a_id, settings=db_settings),
    )
    response = db_client.get(
        "/test/current-space",
        headers={"X-Space-Id": str(user_b_personal_space.id)},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_get_current_space_resolves_membership_for_valid_header(
    db_client,
    migrated_session,
    db_settings,
) -> None:
    user_id = register_user(db_client, "member-lookup@example.com")
    personal_space = await get_personal_space(migrated_session, user_id)

    db_client.cookies.set(
        SESSION_COOKIE_NAME,
        create_session_token(user_id, settings=db_settings),
    )
    response = db_client.get(
        "/test/current-space",
        headers={"X-Space-Id": str(personal_space.id)},
    )

    assert response.status_code == 200
    assert response.json() == {
        "space_id": str(personal_space.id),
        "role": "admin",
    }


async def test_viewer_is_denied_for_member_write_action(
    db_client,
    migrated_session,
    db_settings,
) -> None:
    owner_id = register_user(db_client, "space-owner-write@example.com")
    viewer_id = register_user(db_client, "space-viewer-write@example.com")

    shared_space = Space(
        name="Write-Guarded Space",
        type=SpaceType.SHARED,
        owner_id=owner_id,
    )
    migrated_session.add(shared_space)
    await migrated_session.flush()
    migrated_session.add_all(
        [
            Membership(user_id=owner_id, space_id=shared_space.id, role=MembershipRole.ADMIN),
            Membership(user_id=viewer_id, space_id=shared_space.id, role=MembershipRole.VIEWER),
        ]
    )
    await migrated_session.commit()

    db_client.cookies.set(
        SESSION_COOKIE_NAME,
        create_session_token(viewer_id, settings=db_settings),
    )
    response = db_client.post(
        "/test/current-space/write",
        headers={"X-Space-Id": str(shared_space.id)},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_assert_space_scope_prevents_cross_space_data_leakage(migrated_session) -> None:
    user = User(
        email="scope-user@example.com",
        hashed_password=hash_password("StrongPassword!42"),
    )
    migrated_session.add(user)
    await migrated_session.flush()

    space_a = Space(name="Space A", type=SpaceType.SHARED, owner_id=user.id)
    space_b = Space(name="Space B", type=SpaceType.SHARED, owner_id=user.id)
    migrated_session.add_all([space_a, space_b])
    await migrated_session.flush()

    migrated_session.add_all(
        [
            DashboardPreference(user_id=user.id, space_id=space_a.id, config={"layout": "a"}),
            DashboardPreference(user_id=user.id, space_id=space_b.id, config={"layout": "b"}),
        ]
    )
    await migrated_session.commit()

    unscoped_rows = (await migrated_session.execute(select(DashboardPreference))).scalars().all()
    scoped_rows = (
        await migrated_session.execute(
            assert_space_scope(select(DashboardPreference), space_a.id)
        )
    ).scalars().all()

    assert len(unscoped_rows) == 2
    assert len(scoped_rows) == 1
    assert scoped_rows[0].space_id == space_a.id
