"""add unique index uq_eav_org_entity_code on eav_attributes

Revision ID: d5e6f7a8b9c0
Revises: c0d1e2f3a4b5
Create Date: 2026-08-24
"""

from alembic import op

revision = "d5e6f7a8b9c0"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_eav_org_entity_code",
        "eav_attributes",
        ["org_id", "entity_code", "code"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_eav_org_entity_code", table_name="eav_attributes")
