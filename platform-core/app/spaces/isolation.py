from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.sql import Select


def assert_space_scope(query: Select[tuple[Any]], space_id: uuid.UUID) -> Select[tuple[Any]]:
    if not query.column_descriptions:
        raise ValueError("Query must select at least one mapped entity.")

    for desc in query.column_descriptions:
        entity = desc.get("entity")
        if entity is not None and hasattr(entity, "space_id"):
            return query.where(entity.space_id == space_id)

    raise ValueError("Query must select a mapped entity with a space_id column.")
