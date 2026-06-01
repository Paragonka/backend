from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ReceiptItemCreate(BaseModel):
    product_id: str | None = None
    name: str = Field(..., max_length=255)
    price: Decimal = Field(..., gt=0)
    qty: Decimal = Field(..., gt=0)

    @field_validator("product_id", mode="before")
    @classmethod
    def _coerce_product_id(cls, v: object) -> object:
        if v is None or v == "":
            return None

        try:
            UUID(str(v))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("product_id must be a valid UUID") from None

        return str(v)


class ReceiptItemResponse(BaseModel):
    id: UUID
    receipt_id: UUID
    product_id: UUID | None
    name: str
    price: float
    qty: float

    model_config = {"from_attributes": True}


class ReceiptCreate(BaseModel):
    client_id: str | None = None
    order_id: str | None = None
    receipt_date: str = Field(default="", max_length=32)
    source: str | None = Field(default=None, max_length=50)
    raw_data: dict | None = None
    notes: str | None = None
    items: list[ReceiptItemCreate]


class ReceiptResponse(BaseModel):
    id: UUID
    org_id: UUID
    client_id: UUID | None
    order_id: UUID | None
    receipt_date: str
    total: float
    source: str | None
    raw_data: dict | None
    notes: str | None

    model_config = {"from_attributes": True}


class PaginatedReceipts(BaseModel):
    data: list[ReceiptResponse]
    next_cursor: str | None = None
    total: int | None = None
