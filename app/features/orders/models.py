from decimal import Decimal
from uuid import UUID as PyUUID  # noqa: N811

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TimestampMixin
from app.shared.constants import ORDER_STATUS_DRAFT


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    org_id: Mapped[PyUUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("organizations.id"), index=True
    )
    client_id: Mapped[PyUUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("clients.id"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(20), default=ORDER_STATUS_DRAFT)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    execution_date: Mapped[str] = mapped_column(String(32), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    photos: Mapped[list] = mapped_column(JSONB, default=list)
    local_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    custom_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by: Mapped[PyUUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    updated_by: Mapped[PyUUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )


class OrderItem(TimestampMixin, Base):
    __tablename__ = "order_items"

    order_id: Mapped[PyUUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("orders.id"), index=True
    )
    product_id: Mapped[str | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    qty: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=1)


class WriteOff(TimestampMixin, Base):
    __tablename__ = "write_offs"
    __table_args__ = (
        # At most one write-off per order item: prevents double stock spending.
        Index(
            "uq_write_offs_order_item",
            "order_item_id",
            unique=True,
            postgresql_where=text("order_item_id IS NOT NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    order_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("order_items.id"), nullable=True, index=True
    )
    product_id: Mapped[str | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    reason: Mapped[str] = mapped_column(String(100), default="production")
