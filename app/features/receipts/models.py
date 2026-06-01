from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TimestampMixin


class Receipt(TimestampMixin, Base):
    __tablename__ = "receipts"

    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    client_id: Mapped[str | None] = mapped_column(
        ForeignKey("clients.id"), nullable=True, index=True
    )
    order_id: Mapped[str | None] = mapped_column(
        ForeignKey("orders.id"), nullable=True, index=True
    )
    receipt_date: Mapped[str] = mapped_column(String(32), default="")
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReceiptItem(TimestampMixin, Base):
    __tablename__ = "receipt_items"

    receipt_id: Mapped[str] = mapped_column(ForeignKey("receipts.id"), index=True)
    product_id: Mapped[str | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    qty: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=1)
