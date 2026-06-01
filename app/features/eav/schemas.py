from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.shared.constants import EAV_FIELD_TYPE_STRING


class EavAttributeCreate(BaseModel):
    entity_code: Literal["client", "product", "order"]
    code: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    field_type: str = EAV_FIELD_TYPE_STRING
    is_required: bool = False
    default_value: str = ""


class EavAttributeUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    name: str | None = None
    field_type: str | None = None
    is_required: bool | None = None
    default_value: str | None = None


class EavAttributeResponse(BaseModel):
    id: UUID
    org_id: UUID
    entity_code: str
    code: str
    name: str
    field_type: str
    is_required: bool
    default_value: str

    model_config = {"from_attributes": True}
