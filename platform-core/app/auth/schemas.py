from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.auth.service import check_password_strength

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MAX_BYTES = 72
WEAK_PASSWORD_MESSAGE = (
    "Password must be at least 8 characters long and not be a commonly used password."
)


class AuthCredentialsRequest(BaseModel):
    email: str
    password: str = Field(max_length=72)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Email address must be valid.")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > PASSWORD_MAX_BYTES:
            raise ValueError("Password must be 72 bytes or fewer.")
        if not check_password_strength(value):
            raise ValueError(WEAK_PASSWORD_MESSAGE)
        return value


class LoginRequest(BaseModel):
    email: str
    password: str = Field(max_length=72)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Email address must be valid.")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > PASSWORD_MAX_BYTES:
            raise ValueError("Password must be 72 bytes or fewer.")
        return value


class AuthUserPayload(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    email: str


class AuthUserResponse(BaseModel):
    data: AuthUserPayload


class LogoutPayload(BaseModel):
    status: str


class LogoutResponse(BaseModel):
    data: LogoutPayload
