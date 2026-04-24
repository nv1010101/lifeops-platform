from __future__ import annotations

import logging

from app.config import Settings
from app.registry.config_loader import (
    load_configured_modules,
    load_configured_modules_for_startup,
    parse_modules_config,
)


def _build_settings(modules_config: str | None) -> Settings:
    return Settings(
        _env_file=None,
        app_env="test",
        app_base_url="http://testserver",
        database_url="postgresql+asyncpg://user:pass@127.0.0.1:5432/lifeops_test",
        session_secret="test-session-secret",
        modules_config=modules_config,
    )


def test_config_loader_parses_modules_from_modules_config_env_payload() -> None:
    settings = _build_settings(
        """
        [
          {
            "module_id": "vocabulary",
            "display_name": "Vocabulary",
            "base_url": "http://vocabulary-service:8001",
            "api_version": "1",
            "internal_bearer_token": "token-vocabulary"
          }
        ]
        """
    )

    loaded_modules = load_configured_modules(settings)

    assert len(loaded_modules) == 1
    assert loaded_modules[0].module_id == "vocabulary"
    assert loaded_modules[0].display_name == "Vocabulary"
    assert loaded_modules[0].base_url == "http://vocabulary-service:8001"
    assert loaded_modules[0].api_version == "1"
    assert loaded_modules[0].internal_bearer_token == "token-vocabulary"


def test_config_loader_skips_malformed_module_entries_with_warning(caplog) -> None:
    caplog.set_level(logging.WARNING)

    loaded_modules = parse_modules_config(
        """
        [
          {
            "module_id": "vocabulary",
            "display_name": "Vocabulary",
            "base_url": "http://vocabulary-service:8001",
            "api_version": "1",
            "internal_bearer_token": "token-vocabulary"
          },
          {
            "module_id": "job tracker",
            "display_name": "Job Tracker",
            "base_url": "http://job-tracker:8002",
            "api_version": "1",
            "internal_bearer_token": "token-job-tracker"
          },
          {
            "module_id": "notes",
            "display_name": "Notes",
            "base_url": "http://notes-service:8003",
            "api_version": "1"
          },
          "not-an-object"
        ]
        """
    )

    assert len(loaded_modules) == 1
    assert loaded_modules[0].module_id == "vocabulary"
    assert "Skipping module declaration at index 1 due to invalid fields: module_id" in caplog.text
    assert (
        "Skipping module declaration at index 2 due to invalid fields: internal_bearer_token"
        in caplog.text
    )
    assert "Skipping module declaration at index 3 because it is not an object." in caplog.text


def test_startup_loader_marks_invalid_top_level_json_as_not_applicable() -> None:
    settings = _build_settings("{invalid-json")

    loaded_modules, config_is_valid = load_configured_modules_for_startup(settings)

    assert loaded_modules == []
    assert config_is_valid is False
