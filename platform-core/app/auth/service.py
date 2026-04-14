from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from importlib.resources import files

import bcrypt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.memberships.models import Membership, MembershipRole
from app.spaces.models import Space, SpaceType
from app.users.models import User

SESSION_COOKIE_NAME = "session"
SESSION_MAX_AGE_SECONDS = 24 * 60 * 60
SESSION_IDLE_TIMEOUT_SECONDS = 30 * 60
SESSION_COOKIE_PATH = "/"
SESSION_COOKIE_SAMESITE = "strict"
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(
    b"lifeops-auth-dummy-password",
    bcrypt.gensalt(),
).decode("utf-8")


@dataclass(frozen=True)
class SessionTokenClaims:
    user_id: uuid.UUID
    expires_at: int
    idle_expires_at: int
    issued_at: int


class AuthServiceError(Exception):
    """Base auth service error."""


class DuplicateEmailError(AuthServiceError):
    """Raised when a user with the requested email already exists."""


class InvalidCredentialsError(AuthServiceError):
    """Raised when login credentials are invalid."""


class SessionTokenError(AuthServiceError):
    """Raised when a session token cannot be validated."""


class InvalidSessionTokenError(SessionTokenError):
    """Raised when a session token has been tampered with or is malformed."""


class ExpiredSessionTokenError(SessionTokenError):
    """Raised when a session token has expired."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _resolve_settings(settings: Settings | None) -> Settings:
    return settings or get_settings()


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign_payload_segment(payload_segment: str, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        payload_segment.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _b64url_encode(digest)


@lru_cache(maxsize=1)
def _common_passwords() -> set[str]:
    password_file = files("app.auth").joinpath("common_passwords.txt")
    with password_file.open("r", encoding="utf-8") as handle:
        return {line.strip().casefold() for line in handle if line.strip()}


def _normalize_password_candidate(password: str) -> str:
    return password.strip().casefold()


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


async def hash_password_async(plain: str) -> str:
    return await asyncio.to_thread(hash_password, plain)


async def verify_password_async(plain: str, hashed: str) -> bool:
    return await asyncio.to_thread(verify_password, plain, hashed)


def create_session_token(
    user_id: uuid.UUID,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
    absolute_expires_at: int | None = None,
) -> str:
    current_time = now or _utc_now()
    expires_at = absolute_expires_at or int(
        (current_time + timedelta(seconds=SESSION_MAX_AGE_SECONDS)).timestamp()
    )
    payload = {
        "sub": str(user_id),
        "exp": expires_at,
        "idle_exp": int(
            (current_time + timedelta(seconds=SESSION_IDLE_TIMEOUT_SECONDS)).timestamp()
        ),
        "iat": int(current_time.timestamp()),
        "ver": 1,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_segment = _b64url_encode(payload_bytes)
    session_secret = _resolve_settings(settings).session_secret
    signature_segment = _sign_payload_segment(payload_segment, session_secret)
    return f"{payload_segment}.{signature_segment}"


def decode_session_token_claims(
    token: str,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> SessionTokenClaims:
    try:
        payload_segment, signature_segment = token.split(".", maxsplit=1)
    except ValueError as exc:
        raise InvalidSessionTokenError("Session token is malformed.") from exc

    session_secret = _resolve_settings(settings).session_secret
    expected_signature = _sign_payload_segment(payload_segment, session_secret)
    if not hmac.compare_digest(signature_segment, expected_signature):
        raise InvalidSessionTokenError("Session token signature is invalid.")

    try:
        payload_bytes = _b64url_decode(payload_segment)
    except ValueError as exc:
        raise InvalidSessionTokenError("Session token payload encoding is invalid.") from exc

    try:
        payload = json.loads(payload_bytes)
        user_id = uuid.UUID(payload["sub"])
        expires_at = int(payload["exp"])
        idle_expires_at = int(payload["idle_exp"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise InvalidSessionTokenError("Session token payload is invalid.") from exc

    current_timestamp = int((now or _utc_now()).timestamp())
    if current_timestamp >= expires_at or current_timestamp >= idle_expires_at:
        raise ExpiredSessionTokenError("Session token has expired.")

    return SessionTokenClaims(
        user_id=user_id,
        expires_at=expires_at,
        idle_expires_at=idle_expires_at,
        issued_at=int(payload.get("iat", 0)),
    )


def decode_session_token(
    token: str,
    *,
    settings: Settings | None = None,
    now: datetime | None = None,
) -> uuid.UUID:
    return decode_session_token_claims(token, settings=settings, now=now).user_id


def check_password_strength(password: str) -> bool:
    if len(password) < 8:
        return False
    if len(password.encode("utf-8")) > 72:
        return False
    return _normalize_password_candidate(password) not in _common_passwords()


def get_session_cookie_max_age(
    *,
    expires_at: int,
    now: datetime | None = None,
) -> int:
    current_timestamp = int((now or _utc_now()).timestamp())
    return max(0, expires_at - current_timestamp)


async def _get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


def _is_unique_email_violation(exc: IntegrityError) -> bool:
    return "uq_users_email" in str(exc.orig).lower() or "users_email_key" in str(exc.orig).lower()


async def register_user(session: AsyncSession, *, email: str, password: str) -> User:
    user: User | None = None
    hashed_password = await hash_password_async(password)

    try:
        async with session.begin():
            if await _get_user_by_email(session, email) is not None:
                raise DuplicateEmailError

            user = User(email=email, hashed_password=hashed_password)
            session.add(user)
            await session.flush()

            personal_space = Space(
                name=f"{email}'s space",
                type=SpaceType.PERSONAL,
                owner_id=user.id,
            )
            session.add(personal_space)
            await session.flush()

            membership = Membership(
                user_id=user.id,
                space_id=personal_space.id,
                role=MembershipRole.ADMIN,
            )
            session.add(membership)
    except IntegrityError as exc:
        if _is_unique_email_violation(exc):
            raise DuplicateEmailError from exc
        raise

    if user is None:
        raise RuntimeError("User registration completed without creating a user.")

    return user


async def authenticate_user(session: AsyncSession, *, email: str, password: str) -> User:
    user = await _get_user_by_email(session, email)
    hashed_password = user.hashed_password if user is not None else _DUMMY_PASSWORD_HASH
    is_valid_password = await verify_password_async(password, hashed_password)
    if user is None or not is_valid_password:
        raise InvalidCredentialsError
    return user
