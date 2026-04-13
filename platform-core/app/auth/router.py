from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.auth.schemas import (
    AuthCredentialsRequest,
    AuthUserPayload,
    AuthUserResponse,
    LoginRequest,
    LogoutPayload,
    LogoutResponse,
)
from app.auth.service import (
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_PATH,
    SESSION_COOKIE_SAMESITE,
    DuplicateEmailError,
    InvalidCredentialsError,
    authenticate_user,
    create_session_token,
    decode_session_token_claims,
    get_session_cookie_max_age,
    register_user,
)
from app.dependencies import DatabaseSessionDependency, SettingsDependency
from app.errors import build_error_response

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str, *, settings: SettingsDependency) -> None:
    claims = decode_session_token_claims(token, settings=settings)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=get_session_cookie_max_age(expires_at=claims.expires_at),
        httponly=True,
        path=SESSION_COOKIE_PATH,
        samesite=SESSION_COOKIE_SAMESITE,
        secure=True,
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path=SESSION_COOKIE_PATH,
        httponly=True,
        samesite=SESSION_COOKIE_SAMESITE,
        secure=True,
    )


@router.post("/register", response_model=AuthUserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: AuthCredentialsRequest,
    request: Request,
    db: DatabaseSessionDependency,
) -> AuthUserResponse | Response:
    try:
        user = await register_user(db, email=payload.email, password=payload.password)
    except DuplicateEmailError:
        return build_error_response(
            request,
            status.HTTP_409_CONFLICT,
            code="email_taken",
            message="An account with this email already exists.",
        )

    return AuthUserResponse(
        data=AuthUserPayload(user_id=str(user.id), email=user.email),
    )


@router.post("/login", response_model=AuthUserResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DatabaseSessionDependency,
    settings: SettingsDependency,
) -> AuthUserResponse | Response:
    try:
        user = await authenticate_user(db, email=payload.email, password=payload.password)
    except InvalidCredentialsError:
        return build_error_response(
            request,
            status.HTTP_401_UNAUTHORIZED,
            code="invalid_credentials",
            message="Invalid email or password.",
        )

    session_token = create_session_token(user.id, settings=settings)
    _set_session_cookie(response, session_token, settings=settings)
    return AuthUserResponse(
        data=AuthUserPayload(user_id=str(user.id), email=user.email),
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(response: Response) -> LogoutResponse:
    _clear_session_cookie(response)
    return LogoutResponse(data=LogoutPayload(status="ok"))
