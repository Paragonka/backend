"""add order is_deleted

Revision ID: a1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-08-21
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.create_index(op.f("ix_orders_is_deleted"), "orders", ["is_deleted"])


def downgrade() -> None:
    op.drop_index(op.f("ix_orders_is_deleted"), table_name="orders")
    op.drop_column("orders", "is_deleted")
