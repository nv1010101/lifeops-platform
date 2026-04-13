from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request, Response, status

from app.auth.service import (
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_PATH,
    SESSION_COOKIE_SAMESITE,
    ExpiredSessionTokenError,
    InvalidSessionTokenError,
    create_session_token,
    decode_session_token_claims,
    get_session_cookie_max_age,
)
from app.dependencies import DatabaseSessionDependency, SettingsDependency
from app.errors import ApplicationHTTPException
from app.users.models import User


async def get_current_user(
    request: Request,
    response: Response,
    db: DatabaseSessionDependency,
    settings: SettingsDependency,
) -> User:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise ApplicationHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    try:
        claims = decode_session_token_claims(token, settings=settings)
    except (ExpiredSessionTokenError, InvalidSessionTokenError) as exc:
        raise ApplicationHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            clear_session_cookie=True,
        ) from exc

    user = await db.get(User, claims.user_id)
    if user is None:
        raise ApplicationHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            clear_session_cookie=True,
        )

    refreshed_token = create_session_token(
        user.id,
        settings=settings,
        absolute_expires_at=claims.expires_at,
    )
    max_age = get_session_cookie_max_age(expires_at=claims.expires_at)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=refreshed_token,
        max_age=max_age,
        httponly=True,
        path=SESSION_COOKIE_PATH,
        samesite=SESSION_COOKIE_SAMESITE,
        secure=True,
    )

    return user


CurrentUserDependency = Annotated[User, Depends(get_current_user)]
