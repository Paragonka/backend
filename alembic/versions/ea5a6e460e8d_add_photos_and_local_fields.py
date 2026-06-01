"""add photos and local_fields

Revision ID: ea5a6e460e8d
Revises: b6ff71e3063e
Create Date: 2026-06-07 16:32:52.476404

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ea5a6e460e8d"
down_revision: str | Sequence[str] | None = "b6ff71e3063e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "clients",
        sa.Column(
            "local_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "photos",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "local_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "photos",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "local_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("products", "local_fields")
    op.drop_column("products", "photos")
    op.drop_column("orders", "local_fields")
    op.drop_column("orders", "photos")
    op.drop_column("clients", "local_fields")
