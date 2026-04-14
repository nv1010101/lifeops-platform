from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class CreateSpaceRequest(BaseModel):
    name: str = Field(max_length=255)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Space name must not be empty.")
        return normalized


class SpacePayload(BaseModel):
    space_id: str
    name: str
    type: str


class CreateSpaceResponse(BaseModel):
    data: SpacePayload


class SpaceListItem(BaseModel):
    space_id: str
    name: str
    type: str
    role: str


class SpaceListResponse(BaseModel):
    items: list[SpaceListItem]
    total: int
