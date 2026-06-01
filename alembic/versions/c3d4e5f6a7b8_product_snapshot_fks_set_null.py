"""product deletion: snapshot FKs ON DELETE SET NULL

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a8
Create Date: 2026-08-27 19:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "order_items_product_id_fkey", "order_items", type_="foreignkey"
    )
    op.create_foreign_key(
        "order_items_product_id_fkey",
        "order_items",
        "products",
        ["product_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.alter_column(
        "write_offs", "product_id", existing_type=sa.UUID(), nullable=True
    )
    op.drop_constraint(
        "write_offs_product_id_fkey", "write_offs", type_="foreignkey"
    )
    op.create_foreign_key(
        "write_offs_product_id_fkey",
        "write_offs",
        "products",
        ["product_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint(
        "receipt_items_product_id_fkey", "receipt_items", type_="foreignkey"
    )
    op.create_foreign_key(
        "receipt_items_product_id_fkey",
        "receipt_items",
        "products",
        ["product_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "receipt_items_product_id_fkey", "receipt_items", type_="foreignkey"
    )
    op.create_foreign_key(
        "receipt_items_product_id_fkey",
        "receipt_items",
        "products",
        ["product_id"],
        ["id"],
    )

    op.alter_column(
        "write_offs", "product_id", existing_type=sa.UUID(), nullable=False
    )
    op.drop_constraint(
        "write_offs_product_id_fkey", "write_offs", type_="foreignkey"
    )
    op.create_foreign_key(
        "write_offs_product_id_fkey",
        "write_offs",
        "products",
        ["product_id"],
        ["id"],
    )

    op.drop_constraint(
        "order_items_product_id_fkey", "order_items", type_="foreignkey"
    )
    op.create_foreign_key(
        "order_items_product_id_fkey",
        "order_items",
        "products",
        ["product_id"],
        ["id"],
    )