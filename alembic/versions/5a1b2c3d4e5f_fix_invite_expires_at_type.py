"""fix invite expires_at type

Revision ID: 5a1b2c3d4e5f
Revises: 93178a82767c
Create Date: 2026-07-11 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "5a1b2c3d4e5f"
down_revision: str | Sequence[str] | None = "93178a82767c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "invites",
        "expires_at",
        existing_type=sa.String(length=64),
        type_=sa.DateTime(timezone=True),
        nullable=True,
        postgresql_using="NULLIF(expires_at, '')::timestamp with time zone",
    )


def downgrade() -> None:
    op.alter_column(
        "invites",
        "expires_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.String(length=64),
        nullable=False,
        postgresql_using="expires_at::varchar(64)",
    )
