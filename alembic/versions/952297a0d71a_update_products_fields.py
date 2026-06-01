"""update_products_fields

Revision ID: 952297a0d71a
Revises: a8901f133ddd
Create Date: 2026-06-07 12:37:55.182173

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "952297a0d71a"
down_revision: str | Sequence[str] | None = "a8901f133ddd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("product_type", sa.String(20), server_default="good", nullable=False),
    )
    op.add_column(
        "products",
        sa.Column("cost_price", sa.Numeric(10, 2), server_default="0", nullable=False),
    )
    op.add_column("products", sa.Column("stock_qty", sa.Numeric(10, 2), nullable=True))
    op.add_column(
        "products",
        sa.Column("track_inventory", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "products",
        sa.Column("is_sellable", sa.Integer(), server_default="1", nullable=False),
    )
    op.drop_column("products", "sku")
    op.drop_column("products", "barcode")
    op.drop_column("products", "tax_rate")
    op.drop_column("products", "cost")
    op.drop_column("products", "description")


def downgrade() -> None:
    op.add_column(
        "products",
        sa.Column("description", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "products",
        sa.Column("cost", sa.Numeric(10, 2), server_default="0", nullable=False),
    )
    op.add_column(
        "products",
        sa.Column("tax_rate", sa.Numeric(5, 2), server_default="0", nullable=False),
    )
    op.add_column(
        "products",
        sa.Column("barcode", sa.String(100), server_default="", nullable=False),
    )
    op.add_column(
        "products", sa.Column("sku", sa.String(100), server_default="", nullable=False)
    )
    op.drop_column("products", "is_sellable")
    op.drop_column("products", "track_inventory")
    op.drop_column("products", "stock_qty")
    op.drop_column("products", "cost_price")
    op.drop_column("products", "product_type")
