from functools import lru_cache

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env",),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(default="LifeOps Platform Core", validation_alias="APP_NAME")
    app_env: str = Field(min_length=1, validation_alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", validation_alias="APP_HOST")
    app_port: int = Field(default=8000, validation_alias="APP_PORT")
    app_base_url: str = Field(min_length=1, validation_alias="APP_BASE_URL")
    app_version: str = Field(default="0.1.0", validation_alias="APP_VERSION")
    database_url: str = Field(min_length=1, validation_alias="DATABASE_URL")
    jwt_secret: str = Field(min_length=1, validation_alias="JWT_SECRET")
    default_locale: str = Field(default="en", validation_alias="DEFAULT_LOCALE")
    default_timezone: str = Field(default="UTC", validation_alias="DEFAULT_TIMEZONE")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        missing_fields: list[str] = []
        invalid_fields: list[str] = []

        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"])
            if error["type"] == "missing":
                missing_fields.append(location)
            else:
                invalid_fields.append(f"{location} ({error['msg']})")

        details: list[str] = []
        if missing_fields:
            details.append(
                "missing required settings: " + ", ".join(sorted(missing_fields)),
            )
        if invalid_fields:
            details.append("invalid settings: " + ", ".join(sorted(invalid_fields)))

        message = "; ".join(details) or str(exc)
        raise RuntimeError(f"Invalid application configuration: {message}") from exc
