# Synchronized with frontend/src/shared/constants.ts

from typing import Final, Literal

# Product types
ProductType = Literal["good", "service", "material"]
PRODUCT_TYPE_GOOD: Final[ProductType] = "good"
PRODUCT_TYPE_SERVICE: Final[ProductType] = "service"
PRODUCT_TYPE_MATERIAL: Final[ProductType] = "material"
PRODUCT_TYPES: Final[list[str]] = [
    PRODUCT_TYPE_GOOD,
    PRODUCT_TYPE_SERVICE,
    PRODUCT_TYPE_MATERIAL,
]

# Order statuses
ORDER_STATUS_DRAFT: Final[str] = "draft"
ORDER_STATUS_CONFIRMED: Final[str] = "confirmed"
ORDER_STATUS_DONE: Final[str] = "done"
ORDER_STATUS_CANCELLED: Final[str] = "cancelled"
ORDER_STATUSES: Final[list[str]] = [
    ORDER_STATUS_DRAFT,
    ORDER_STATUS_CONFIRMED,
    ORDER_STATUS_DONE,
    ORDER_STATUS_CANCELLED,
]

# EAV field types
EAV_FIELD_TYPE_STRING: Final[str] = "string"
EAV_FIELD_TYPE_NUMBER: Final[str] = "number"
EAV_FIELD_TYPE_BOOLEAN: Final[str] = "boolean"
EAV_FIELD_TYPE_DATE: Final[str] = "date"
EAV_FIELD_TYPE_TEXT: Final[str] = "text"
EAV_FIELD_TYPES: Final[list[str]] = [
    EAV_FIELD_TYPE_STRING,
    EAV_FIELD_TYPE_NUMBER,
    EAV_FIELD_TYPE_BOOLEAN,
    EAV_FIELD_TYPE_DATE,
    EAV_FIELD_TYPE_TEXT,
]

# Entity types
ENTITY_TYPE_CLIENT: Final[str] = "client"
ENTITY_TYPE_PRODUCT: Final[str] = "product"
ENTITY_TYPE_ORDER: Final[str] = "order"
ENTITY_TYPES: Final[list[str]] = [
    ENTITY_TYPE_CLIENT,
    ENTITY_TYPE_PRODUCT,
    ENTITY_TYPE_ORDER,
]
