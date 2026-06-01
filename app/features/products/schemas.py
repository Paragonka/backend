from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.shared.constants import PRODUCT_TYPE_GOOD, ProductType


class ProductComponentInput(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(..., gt=0)


class ProductComponentResponse(BaseModel):
    product_id: UUID
    quantity: float

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    name: str = Field(..., max_length=255)
    category: str = ""
    unit: str = "шт"
    product_type: ProductType = PRODUCT_TYPE_GOOD
    price: Decimal = Field(default=Decimal("0"), ge=0)
    cost_price: Decimal = Field(default=Decimal("0"), ge=0)
    stock_qty: Decimal | None = None
    track_inventory: bool = False
    is_sellable: bool = True
    is_active: bool = True
    custom_fields: dict | None = None
    local_fields: dict | None = None
    components: list[ProductComponentInput] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    category: str | None = None
    unit: str | None = None
    product_type: ProductType | None = None
    price: Decimal | None = Field(default=None, ge=0)
    cost_price: Decimal | None = Field(default=None, ge=0)
    stock_qty: Decimal | None = None
    track_inventory: bool | None = None
    is_sellable: bool | None = None
    is_active: bool | None = None
    components: list[ProductComponentInput] | None = None
    local_fields: dict | None = None


class ProductResponse(BaseModel):
    id: UUID
    org_id: UUID
    category: str
    name: str
    unit: str
    product_type: str
    price: float
    cost_price: float
    stock_qty: float | None
    track_inventory: bool
    is_sellable: bool
    is_active: bool
    custom_fields: dict = Field(default_factory=dict)
    photos: list = Field(default_factory=list)
    local_fields: dict = Field(default_factory=dict)
    components: list[ProductComponentResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}

    @field_validator("custom_fields", "local_fields", mode="before")
    @classmethod
    def coerce_dict(cls, v: object) -> object:
        if isinstance(v, list):
            return {}

        if not isinstance(v, dict):
            return {}

        return v


class PaginatedProducts(BaseModel):
    data: list[ProductResponse]
    next_cursor: str | None = None
    total: int = 0
