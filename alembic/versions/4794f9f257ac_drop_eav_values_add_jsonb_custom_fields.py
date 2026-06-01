"""drop_eav_values_add_jsonb_custom_fields

Revision ID: 4794f9f257ac
Revises: 7a26e8efb2e4
Create Date: 2026-06-07 11:13:52.519166

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "4794f9f257ac"
down_revision: str | Sequence[str] | None = "7a26e8efb2e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("eav_values")
    op.add_column(
        "clients",
        sa.Column(
            "custom_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "custom_fields",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.create_table(
        "eav_values",
        sa.Column("attribute_id", sa.UUID(), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["attribute_id"], ["eav_attributes.id"]),
        sa.PrimaryKeyConstraint("attribute_id", "entity_id"),
    )
    op.drop_column("products", "custom_fields")
    op.drop_column("clients", "custom_fields")
