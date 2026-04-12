from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


def test_health_returns_ok(monkeypatch) -> None:
    monkeypatch.setenv("APP_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://lifeops:lifeops@localhost:5432/lifeops",
    )
    get_settings.cache_clear()

    try:
        client = TestClient(create_app())
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    finally:
        get_settings.cache_clear()
