"""add clients is_archived

Revision ID: c0d1e2f3a4b5
Revises: a1b2c3d4e5f6
Create Date: 2026-08-24
"""

from alembic import op
import sqlalchemy as sa

revision = "c0d1e2f3a4b5"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column(
            "is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )
    op.create_index("ix_clients_org_archived", "clients", ["org_id", "is_archived"])


def downgrade() -> None:
    op.drop_index("ix_clients_org_archived", table_name="clients")
    op.drop_column("clients", "is_archived")
