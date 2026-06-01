"""update_clients_fields

Revision ID: a8901f133ddd
Revises: 4794f9f257ac
Create Date: 2026-06-07 12:35:45.335579

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a8901f133ddd"
down_revision: str | Sequence[str] | None = "4794f9f257ac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column("surname", sa.String(255), server_default="", nullable=False),
    )
    op.drop_column("clients", "email")
    op.drop_column("clients", "birth_date")
    op.drop_column("clients", "loyalty_points")


def downgrade() -> None:
    op.add_column(
        "clients",
        sa.Column("loyalty_points", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "clients",
        sa.Column("birth_date", sa.String(10), server_default="", nullable=False),
    )
    op.add_column(
        "clients", sa.Column("email", sa.String(255), server_default="", nullable=False)
    )
    op.drop_column("clients", "surname")
