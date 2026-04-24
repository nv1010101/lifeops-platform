from __future__ import annotations


async def test_registry_modules_returns_empty_list_when_no_modules_are_configured(
    db_client,
) -> None:
    response = db_client.get("/registry/modules")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}
