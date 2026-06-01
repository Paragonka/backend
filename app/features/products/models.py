from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import Base, TimestampMixin
from app.shared.constants import PRODUCT_TYPE_GOOD


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        Index("uq_products_org_name_unit", "org_id", "name", "unit", unique=True),
    )

    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(255), default="")
    unit: Mapped[str] = mapped_column(String(20), default="шт")
    product_type: Mapped[str] = mapped_column(String(20), default=PRODUCT_TYPE_GOOD)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    cost_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    stock_qty: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True, default=None
    )
    track_inventory: Mapped[bool] = mapped_column(Boolean, default=False)
    is_sellable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    custom_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    photos: Mapped[list] = mapped_column(JSONB, default=list)
    local_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    components: Mapped[list[ProductComponent]] = relationship(
        "ProductComponent",
        foreign_keys="ProductComponent.product_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )


class ProductComponent(Base):
    """A product used to make another product, with its required quantity."""

    __tablename__ = "product_components"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_product_components_quantity_positive"),
        # component_id lookups (exists_as_component) are not covered by the
        # composite primary key (product_id, component_id).
        Index("ix_product_components_component_id", "component_id"),
    )

    product_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
    )
    component_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
