from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ClientCreate(BaseModel):
    name: str = Field(..., max_length=255)
    surname: str = Field(default="", max_length=255)
    phone: str = Field(default="", max_length=20)
    notes: str = ""
    custom_fields: dict | None = None
    local_fields: dict | None = None


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    surname: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    notes: str | None = None
    custom_fields: dict | None = None
    local_fields: dict | None = None


class ClientResponse(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    surname: str
    phone: str
    notes: str
    custom_fields: dict = {}
    local_fields: dict = {}
    photos: list[str] = []
    is_archived: bool = False

    model_config = {"from_attributes": True}

    @field_validator("custom_fields", "local_fields", mode="before")
    @classmethod
    def coerce_dict(cls, v: object) -> object:
        if isinstance(v, list):
            return {}

        return v


class PaginatedClients(BaseModel):
    data: list[ClientResponse]
    next_cursor: str | None = None
    total: int = 0
