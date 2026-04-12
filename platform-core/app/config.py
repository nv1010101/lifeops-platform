from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="LifeOps Platform Core", validation_alias="APP_NAME")
    app_env: str = Field(default="local", validation_alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", validation_alias="APP_HOST")
    app_port: int = Field(default=8000, validation_alias="APP_PORT")
    app_base_url: str = Field(validation_alias="APP_BASE_URL")
    app_version: str = Field(default="0.1.0", validation_alias="APP_VERSION")
    database_url: str = Field(validation_alias="DATABASE_URL")
    default_locale: str = Field(default="en", validation_alias="DEFAULT_LOCALE")
    default_timezone: str = Field(default="UTC", validation_alias="DEFAULT_TIMEZONE")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
