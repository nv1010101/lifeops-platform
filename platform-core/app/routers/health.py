from fastapi import APIRouter

from app.dependencies import SettingsDependency

router = APIRouter(tags=["health"])


@router.get("/health")
def healthcheck(settings: SettingsDependency) -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}
