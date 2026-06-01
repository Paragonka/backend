import re
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# the calendar/finances rely on lexicographic string ordering,
# so the format is strictly fixed (zero-padding is required).
_EXECUTION_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EXECUTION_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")


def validate_execution_date(value: str) -> str:
    """Empty string OR YYYY-MM-DD / YYYY-MM-DD HH:MM, otherwise ValueError (-> 422)."""

    if value == "":
        return value

    if _EXECUTION_DATE_RE.match(value):
        datetime.strptime(value, "%Y-%m-%d")

        return value

    if _EXECUTION_DATETIME_RE.match(value):
        datetime.strptime(value, "%Y-%m-%d %H:%M")

        return value

    raise ValueError(
        "execution_date must be empty or in 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM' format"
    )


class OrderItemCreate(BaseModel):
    product_id: str | None = None
    name: str = Field(..., max_length=255)
    price: Decimal = Field(default=Decimal("0"), ge=0)
    qty: Decimal = Field(default=Decimal(1), gt=0)


class OrderItemUpdate(BaseModel):
    name: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    qty: Decimal | None = Field(default=None, gt=0)


class OrderItemResponse(BaseModel):
    id: UUID
    order_id: UUID
    product_id: UUID | None
    name: str
    price: float
    qty: float

    model_config = {"from_attributes": True}


class OrderCreate(BaseModel):
    client_id: str | None = None
    execution_date: str = ""
    notes: str = ""
    local_fields: dict | None = None
    custom_fields: dict | None = None
    items: list[OrderItemCreate] = Field(default_factory=list)

    @field_validator("execution_date")
    @classmethod
    def _valid_execution_date(cls, v: str) -> str:
        return validate_execution_date(v)


class OrderResponse(BaseModel):
    id: UUID
    org_id: UUID
    client_id: UUID | None
    client_name: str = ""
    status: str
    total: float
    execution_date: str
    notes: str
    photos: list = []
    local_fields: dict = {}
    custom_fields: dict = {}
    is_deleted: bool = False
    items: list[OrderItemResponse] = []

    model_config = {"from_attributes": True}

    @field_validator("custom_fields", "local_fields", mode="before")
    @classmethod
    def coerce_dict(cls, v: object) -> object:
        if isinstance(v, list):
            return {}

        return v


class PaginatedOrders(BaseModel):
    data: list[OrderResponse]
    next_cursor: str | None = None
    total: int = 0


class StatusUpdate(BaseModel):
    status: Literal["draft", "confirmed", "done", "cancelled"]


class WriteOffItemCreate(BaseModel):
    order_item_id: UUID
    qty: Decimal = Field(..., gt=0)
    reason: str | None = Field(default=None, max_length=100)


class WriteOffResponse(BaseModel):
    id: UUID
    product_id: UUID
    qty: Decimal
    reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
