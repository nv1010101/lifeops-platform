from typing import Any
from sqlalchemy import select
from sqlalchemy.sql import Select
from app.model_registry import load_all_models
from app.users.models import User
from app.memberships.models import Membership
import uuid

def assert_space_scope(query: Select[tuple[Any]], space_id: uuid.UUID) -> Select[tuple[Any]]:
    if not query.column_descriptions:
        raise ValueError("Query must select at least one mapped entity.")

    for desc in query.column_descriptions:
        entity = desc.get("entity")
        if entity is not None and hasattr(entity, "space_id"):
            return query.where(entity.space_id == space_id)

    raise ValueError("Query must select a mapped entity with a space_id column.")

load_all_models()
q = select(User, Membership).join(Membership)
print(assert_space_scope(q, uuid.uuid4()))
