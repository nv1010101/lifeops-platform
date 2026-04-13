def test_health_returns_ok_and_env(client) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "env": "test"}
    assert response.headers["X-Request-Id"]
    assert response.headers["X-Correlation-Id"]
