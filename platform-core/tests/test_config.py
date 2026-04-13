from __future__ import annotations

import pytest

from app.main import create_app


def test_missing_database_url_causes_startup_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_app()
