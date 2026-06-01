"""add created_by / updated_by to clients, products, orders, receipts

Revision ID: a2b3c4d5e6f7
Revises: f0a1b2c3d4e5
Create Date: 2026-08-20 14:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: str | Sequence[str] | None = "f0a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


AUDITED_TABLES = ("clients", "products", "orders", "receipts")


def upgrade() -> None:
    for table in AUDITED_TABLES:
        op.add_column(
            table,
            sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        )
    op.create_index("ix_clients_created_by", "clients", ["created_by"])
    op.create_index("ix_products_created_by", "products", ["created_by"])
    op.create_index("ix_orders_created_by", "orders", ["created_by"])
    op.create_index("ix_receipts_created_by", "receipts", ["created_by"])


def downgrade() -> None:
    for table in AUDITED_TABLES:
        op.drop_index(f"ix_{table}_created_by", table_name=table)
        op.drop_column(table, "updated_by")
        op.drop_column(table, "created_by")