"""fix products boolean columns + widen execution_date + fix eav is_required

Revision ID: b1c2d3e4f5a6
Revises: 5a1b2c3d4e5f
Create Date: 2026-08-18 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: str | Sequence[str] | None = "5a1b2c3d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE products ALTER COLUMN track_inventory DROP DEFAULT")
    op.execute("ALTER TABLE products ALTER COLUMN is_sellable DROP DEFAULT")
    op.execute("ALTER TABLE products ALTER COLUMN is_active DROP DEFAULT")
    op.alter_column(
        "products",
        "track_inventory",
        existing_type=sa.Integer(),
        type_=sa.Boolean(),
        nullable=False,
        postgresql_using="track_inventory::boolean",
    )
    op.alter_column(
        "products",
        "is_sellable",
        existing_type=sa.Integer(),
        type_=sa.Boolean(),
        nullable=False,
        postgresql_using="is_sellable::boolean",
    )
    op.alter_column(
        "products",
        "is_active",
        existing_type=sa.Integer(),
        type_=sa.Boolean(),
        nullable=False,
        postgresql_using="is_active::boolean",
    )
    op.alter_column(
        "products",
        "track_inventory",
        existing_type=sa.Boolean(),
        server_default=sa.text("false"),
    )
    op.alter_column(
        "products",
        "is_sellable",
        existing_type=sa.Boolean(),
        server_default=sa.text("true"),
    )
    op.alter_column(
        "products",
        "is_active",
        existing_type=sa.Boolean(),
        server_default=sa.text("true"),
    )
    op.alter_column(
        "orders",
        "execution_date",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        nullable=False,
        server_default="",
    )


def downgrade() -> None:
    op.alter_column(
        "products",
        "track_inventory",
        existing_type=sa.Boolean(),
        type_=sa.Integer(),
        nullable=False,
        server_default="0",
        postgresql_using="CASE WHEN track_inventory THEN 1 ELSE 0 END",
    )
    op.alter_column(
        "products",
        "is_sellable",
        existing_type=sa.Boolean(),
        type_=sa.Integer(),
        nullable=False,
        server_default="1",
        postgresql_using="CASE WHEN is_sellable THEN 1 ELSE 0 END",
    )
    op.alter_column(
        "products",
        "is_active",
        existing_type=sa.Boolean(),
        type_=sa.Integer(),
        nullable=False,
        server_default="1",
        postgresql_using="CASE WHEN is_active THEN 1 ELSE 0 END",
    )
    op.alter_column(
        "orders",
        "execution_date",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
        nullable=False,
        server_default="",
    )
