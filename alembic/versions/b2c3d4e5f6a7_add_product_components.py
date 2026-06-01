"""add product components

Revision ID: b2c3d4e5f6a7
Revises: f1a2b3c4d5e6
Create Date: 2026-08-27 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_components",
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("component_id", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False),
        sa.CheckConstraint(
            "quantity > 0", name="ck_product_components_quantity_positive"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["component_id"], ["products.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("product_id", "component_id"),
    )
    op.create_index(
        "ix_product_components_component_id",
        "product_components",
        ["component_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_components_component_id", table_name="product_components"
    )
    op.drop_table("product_components")
