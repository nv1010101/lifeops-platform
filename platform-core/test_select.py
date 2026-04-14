from sqlalchemy import select
from app.model_registry import load_all_models
from app.dashboard.models import DashboardPreference

load_all_models()
q = select(DashboardPreference.config)
print(q.column_descriptions[0].get("entity"))
