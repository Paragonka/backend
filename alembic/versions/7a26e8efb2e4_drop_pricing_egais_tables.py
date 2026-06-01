"""drop_pricing_egais_tables

Revision ID: 7a26e8efb2e4
Revises: 44596e638f79
Create Date: 2026-06-07 11:13:52.519166

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7a26e8efb2e4"
down_revision: str | Sequence[str] | None = "44596e638f79"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("alcohol_products")
    op.drop_table("alcohol_licenses")
    op.drop_table("discount_rules")
    op.drop_table("tax_rates")


def downgrade() -> None:
    op.create_table(
        "tax_rates",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("is_default", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tax_rates_org_id"), "tax_rates", ["org_id"], unique=False)

    op.create_table(
        "discount_rules",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("discount_type", sa.String(length=20), nullable=False),
        sa.Column("value", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("min_purchase", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("is_active", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_discount_rules_org_id"), "discount_rules", ["org_id"], unique=False
    )

    op.create_table(
        "alcohol_licenses",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("license_number", sa.String(length=100), nullable=False),
        sa.Column("license_type", sa.String(length=50), nullable=False),
        sa.Column("issued_date", sa.String(length=10), nullable=False),
        sa.Column("expiry_date", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_alcohol_licenses_org_id"), "alcohol_licenses", ["org_id"], unique=False
    )

    op.create_table(
        "alcohol_products",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("egais_code", sa.String(length=255), nullable=False),
        sa.Column("alcohol_percent", sa.String(length=10), nullable=False),
        sa.Column("volume", sa.String(length=50), nullable=False),
        sa.Column("license_number", sa.String(length=100), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_alcohol_products_org_id"), "alcohol_products", ["org_id"], unique=False
    )
    op.create_index(
        op.f("ix_alcohol_products_product_id"),
        "alcohol_products",
        ["product_id"],
        unique=False,
    )
