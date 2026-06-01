"""add user_orgs.role and invites.created_by/used_at for H11

Revision ID: e7f8a9b0c1d2
Revises: d5e6f7a8b9c0
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e7f8a9b0c1d2"
down_revision: str | Sequence[str] | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_orgs",
        sa.Column(
            "role", sa.String(length=16), nullable=False, server_default="member"
        ),
    )
    op.add_column("invites", sa.Column("created_by", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_invites_created_by_users", "invites", "users", ["created_by"], ["id"]
    )
    op.add_column(
        "invites", sa.Column("used_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("invites", "used_at")
    op.drop_constraint("fk_invites_created_by_users", "invites", type_="foreignkey")
    op.drop_column("invites", "created_by")
    op.drop_column("user_orgs", "role")
