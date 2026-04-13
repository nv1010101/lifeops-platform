from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie

from sqlalchemy import select

from app.auth.service import (
    SESSION_COOKIE_NAME,
    create_session_token,
    decode_session_token_claims,
    hash_password,
)
from app.memberships.models import Membership, MembershipRole
from app.spaces.models import Space, SpaceType
from app.users.models import User


async def test_register_creates_user_personal_space_and_membership_atomically(
    db_client,
    migrated_session,
) -> None:
    response = db_client.post(
        "/auth/register",
        json={"email": "new-user@example.com", "password": "StrongPassword!42"},
    )

    assert response.status_code == 201
    assert response.json() == {
        "data": {
            "user_id": response.json()["data"]["user_id"],
            "email": "new-user@example.com",
        }
    }

    created_user_id = uuid.UUID(response.json()["data"]["user_id"])
    created_user = await migrated_session.get(User, created_user_id)
    assert created_user is not None
    assert created_user.email == "new-user@example.com"
    assert created_user.hashed_password != "StrongPassword!42"

    created_space = (
        await migrated_session.execute(
        select(Space).where(Space.owner_id == created_user_id)
        )
    ).scalar_one()
    assert created_space.type is SpaceType.PERSONAL
    assert created_space.name == "new-user@example.com's space"

    created_membership = (
        await migrated_session.execute(
        select(Membership).where(
            Membership.user_id == created_user_id,
            Membership.space_id == created_space.id,
        )
        )
    ).scalar_one()
    assert created_membership.role is MembershipRole.ADMIN


def test_register_with_duplicate_email_returns_conflict_code(db_client) -> None:
    first_response = db_client.post(
        "/auth/register",
        json={"email": "duplicate@example.com", "password": "StrongPassword!42"},
    )
    second_response = db_client.post(
        "/auth/register",
        json={"email": "duplicate@example.com", "password": "StrongPassword!42"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["error"]["code"] == "email_taken"


def test_register_with_weak_password_returns_validation_error(db_client) -> None:
    response = db_client.post(
        "/auth/register",
        json={"email": "weak-password@example.com", "password": "password"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "commonly used password" in str(response.json()["error"]["details"])


def test_register_with_password_longer_than_bcrypt_limit_returns_validation_error(
    db_client,
) -> None:
    response = db_client.post(
        "/auth/register",
        json={"email": "too-long@example.com", "password": "a" * 73},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "at most 72 characters" in str(response.json()["error"]["details"])


async def test_login_with_valid_credentials_sets_http_only_session_cookie(
    db_client,
    migrated_session,
) -> None:
    user = User(email="login-user@example.com", hashed_password=hash_password("StrongPassword!42"))
    migrated_session.add(user)
    await migrated_session.commit()

    response = db_client.post(
        "/auth/login",
        json={"email": "login-user@example.com", "password": "StrongPassword!42"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["email"] == "login-user@example.com"
    set_cookie_header = response.headers["set-cookie"]
    cookie = SimpleCookie()
    cookie.load(set_cookie_header)
    assert f"{SESSION_COOKIE_NAME}=" in set_cookie_header
    assert 86399 <= int(cookie[SESSION_COOKIE_NAME]["max-age"]) <= 86400
    assert "HttpOnly" in set_cookie_header
    assert "Secure" in set_cookie_header
    assert "SameSite=strict" in set_cookie_header
    assert "Path=/" in set_cookie_header


async def test_login_with_wrong_password_returns_invalid_credentials_code(
    db_client,
    migrated_session,
) -> None:
    user = User(
        email="wrong-password@example.com",
        hashed_password=hash_password("StrongPassword!42"),
    )
    migrated_session.add(user)
    await migrated_session.commit()

    response = db_client.post(
        "/auth/login",
        json={"email": "wrong-password@example.com", "password": "WrongPassword!42"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_logout_clears_session_cookie(db_client) -> None:
    response = db_client.post("/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"data": {"status": "ok"}}
    set_cookie_header = response.headers["set-cookie"]
    assert f"{SESSION_COOKIE_NAME}=" in set_cookie_header
    assert "Max-Age=0" in set_cookie_header


async def test_authenticated_request_with_valid_session_cookie_resolves_current_user(
    db_client,
    migrated_session,
    db_settings,
) -> None:
    user = User(
        email="current-user@example.com",
        hashed_password=hash_password("StrongPassword!42"),
    )
    migrated_session.add(user)
    await migrated_session.commit()

    session_cookie = create_session_token(user.id, settings=db_settings)
    db_client.cookies.set(SESSION_COOKIE_NAME, session_cookie)
    response = db_client.get("/test/protected")

    assert response.status_code == 200
    assert response.json() == {
        "user_id": str(user.id),
        "email": "current-user@example.com",
    }
    assert f"{SESSION_COOKIE_NAME}=" in response.headers["set-cookie"]


async def test_authenticated_request_refreshes_idle_window_without_extending_absolute_ttl(
    db_client,
    migrated_session,
    db_settings,
) -> None:
    user = User(
        email="ttl-user@example.com",
        hashed_password=hash_password("StrongPassword!42"),
    )
    migrated_session.add(user)
    await migrated_session.commit()

    now = datetime.now(UTC)
    absolute_expires_at = int((now + timedelta(minutes=10)).timestamp())
    original_issued_at = now - timedelta(minutes=20)
    original_token = create_session_token(
        user.id,
        settings=db_settings,
        now=original_issued_at,
        absolute_expires_at=absolute_expires_at,
    )
    original_claims = decode_session_token_claims(
        original_token,
        settings=db_settings,
        now=now,
    )

    db_client.cookies.set(SESSION_COOKIE_NAME, original_token)
    response = db_client.get("/test/protected")

    assert response.status_code == 200
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    refreshed_token = cookie[SESSION_COOKIE_NAME].value
    refreshed_claims = decode_session_token_claims(
        refreshed_token,
        settings=db_settings,
        now=now,
    )

    assert refreshed_claims.expires_at == original_claims.expires_at
    assert refreshed_claims.idle_expires_at > original_claims.idle_expires_at
    assert 1 <= int(cookie[SESSION_COOKIE_NAME]["max-age"]) <= 600


async def test_authenticated_request_with_expired_session_cookie_returns_unauthorized(
    db_client,
    migrated_session,
    db_settings,
) -> None:
    user = User(
        email="expired-session@example.com",
        hashed_password=hash_password("StrongPassword!42"),
    )
    migrated_session.add(user)
    await migrated_session.commit()

    expired_token = create_session_token(
        user.id,
        settings=db_settings,
        now=datetime.now(UTC) - timedelta(hours=25),
    )
    db_client.cookies.set(SESSION_COOKIE_NAME, expired_token)
    response = db_client.get("/test/protected")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_authenticated_request_with_tampered_session_cookie_returns_unauthorized_and_clears_cookie(
    db_client,
    db_settings,
) -> None:
    token = create_session_token(uuid.uuid4(), settings=db_settings)
    tampered_token = token[:-1] + ("a" if token[-1] != "a" else "b")

    db_client.cookies.set(SESSION_COOKIE_NAME, tampered_token)
    response = db_client.get("/test/protected")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_authenticated_request_without_cookie_returns_unauthorized(db_client) -> None:
    response = db_client.get("/test/protected")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
