from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.auth.service import (
    ExpiredSessionTokenError,
    InvalidSessionTokenError,
    check_password_strength,
    create_session_token,
    decode_session_token,
    decode_session_token_claims,
    get_session_cookie_max_age,
    hash_password,
    verify_password,
)
from app.config import Settings


def build_test_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        app_base_url="http://testserver",
        database_url="postgresql+asyncpg://unused:unused@127.0.0.1:1/test",
        session_secret="test-session-secret",
    )


def test_hash_password_uses_salt_for_same_input() -> None:
    password = "ExamplePassword123!"

    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash != second_hash
    assert verify_password(password, first_hash)
    assert verify_password(password, second_hash)


def test_verify_password_accepts_valid_password_and_rejects_invalid_password() -> None:
    hashed_password = hash_password("CorrectHorseBatteryStaple")

    assert verify_password("CorrectHorseBatteryStaple", hashed_password) is True
    assert verify_password("wrong-password", hashed_password) is False


def test_decode_session_token_raises_on_expired_token() -> None:
    user_id = uuid.uuid4()
    settings = build_test_settings()
    issued_at = datetime.now(UTC) - timedelta(hours=25)
    token = create_session_token(user_id, settings=settings, now=issued_at)

    with pytest.raises(ExpiredSessionTokenError):
        decode_session_token(token, settings=settings)


def test_decode_session_token_raises_on_tampered_token() -> None:
    user_id = uuid.uuid4()
    settings = build_test_settings()
    token = create_session_token(user_id, settings=settings)
    tampered_token = token[:-1] + ("a" if token[-1] != "a" else "b")

    with pytest.raises(InvalidSessionTokenError):
        decode_session_token(tampered_token, settings=settings)


def test_decode_session_token_rejects_non_canonical_payload_segment() -> None:
    user_id = uuid.uuid4()
    settings = build_test_settings()
    token = create_session_token(user_id, settings=settings)
    payload_segment, signature_segment = token.split(".", maxsplit=1)
    non_canonical_token = f"{payload_segment}==.{signature_segment}"

    with pytest.raises(InvalidSessionTokenError):
        decode_session_token(non_canonical_token, settings=settings)


def test_refreshed_session_token_can_preserve_absolute_expiry() -> None:
    user_id = uuid.uuid4()
    settings = build_test_settings()
    issued_at = datetime.now(UTC)
    original_token = create_session_token(user_id, settings=settings, now=issued_at)
    original_claims = decode_session_token_claims(original_token, settings=settings, now=issued_at)

    refreshed_token = create_session_token(
        user_id,
        settings=settings,
        now=issued_at + timedelta(minutes=10),
        absolute_expires_at=original_claims.expires_at,
    )
    refreshed_claims = decode_session_token_claims(
        refreshed_token,
        settings=settings,
        now=issued_at + timedelta(minutes=10),
    )

    assert refreshed_claims.expires_at == original_claims.expires_at
    assert refreshed_claims.idle_expires_at > original_claims.idle_expires_at


def test_get_session_cookie_max_age_returns_remaining_absolute_ttl() -> None:
    now = datetime.now(UTC)
    expires_at = int((now + timedelta(minutes=5)).timestamp())

    assert get_session_cookie_max_age(expires_at=expires_at, now=now) == 300


@pytest.mark.parametrize(
    ("password", "expected"),
    [
        ("short", False),
        ("password", False),
        ("a" * 73, False),
        ("StrongPassword!42", True),
    ],
)
def test_check_password_strength_rejects_short_and_common_passwords(
    password: str,
    expected: bool,
) -> None:
    assert check_password_strength(password) is expected
