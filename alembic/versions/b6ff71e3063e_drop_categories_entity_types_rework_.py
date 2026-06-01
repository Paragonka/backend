"""drop_categories_entity_types_rework_writeoffs

Revision ID: b6ff71e3063e
Revises: f776b3b0cfa8
Create Date: 2026-06-07 13:19:40.336118

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6ff71e3063e"
down_revision: str | Sequence[str] | None = "f776b3b0cfa8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create new write_offs table
    op.create_table(
        "write_offs",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("order_item_id", sa.UUID(), nullable=True),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("qty", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("reason", sa.String(length=100), nullable=False),
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
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_write_offs_order_item_id"),
        "write_offs",
        ["order_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_write_offs_org_id"), "write_offs", ["org_id"], unique=False
    )
    op.create_index(
        op.f("ix_write_offs_product_id"), "write_offs", ["product_id"], unique=False
    )

    # Drop old tables with CASCADE to handle FKs
    op.drop_table("order_item_write_offs")
    op.execute("DROP TABLE entity_types CASCADE")
    op.execute("DROP TABLE product_categories CASCADE")

    # Drop old FK columns
    op.drop_index(op.f("ix_eav_attributes_entity_type_id"), table_name="eav_attributes")
    op.drop_column("eav_attributes", "entity_type_id")
    op.drop_index(op.f("ix_products_category_id"), table_name="products")
    op.drop_column("products", "category_id")

    # Add new columns (with server_default for existing rows)
    op.add_column(
        "eav_attributes",
        sa.Column(
            "entity_code", sa.String(length=100), nullable=False, server_default=""
        ),
    )
    op.add_column(
        "products",
        sa.Column("category", sa.String(length=255), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.add_column(
        "products",
        sa.Column("category_id", sa.UUID(), autoincrement=False, nullable=True),
    )
    op.create_foreign_key(
        op.f("products_category_id_fkey"),
        "products",
        "product_categories",
        ["category_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_products_category_id"), "products", ["category_id"], unique=False
    )
    op.drop_column("products", "category")
    op.add_column(
        "eav_attributes",
        sa.Column("entity_type_id", sa.UUID(), autoincrement=False, nullable=False),
    )
    op.create_foreign_key(
        op.f("eav_attributes_entity_type_id_fkey"),
        "eav_attributes",
        "entity_types",
        ["entity_type_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_eav_attributes_entity_type_id"),
        "eav_attributes",
        ["entity_type_id"],
        unique=False,
    )
    op.drop_column("eav_attributes", "entity_code")
    op.create_table(
        "product_categories",
        sa.Column("org_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("name", sa.VARCHAR(length=255), autoincrement=False, nullable=False),
        sa.Column("description", sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("product_categories_org_id_fkey"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("product_categories_pkey")),
    )
    op.create_index(
        op.f("ix_product_categories_org_id"),
        "product_categories",
        ["org_id"],
        unique=False,
    )
    op.create_table(
        "entity_types",
        sa.Column("org_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("code", sa.VARCHAR(length=100), autoincrement=False, nullable=False),
        sa.Column("name", sa.VARCHAR(length=255), autoincrement=False, nullable=False),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"], ["organizations.id"], name=op.f("entity_types_org_id_fkey")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("entity_types_pkey")),
    )
    op.create_index(
        op.f("ix_entity_types_org_id"), "entity_types", ["org_id"], unique=False
    )
    op.create_table(
        "order_item_write_offs",
        sa.Column("order_item_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("product_id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "qty",
            sa.NUMERIC(precision=10, scale=2),
            server_default=sa.text("'0'::numeric"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["order_item_id"],
            ["order_items.id"],
            name=op.f("order_item_write_offs_order_item_id_fkey"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("order_item_write_offs_product_id_fkey"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("order_item_write_offs_pkey")),
    )
    op.create_index(
        op.f("ix_order_item_write_offs_product_id"),
        "order_item_write_offs",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_order_item_write_offs_order_item_id"),
        "order_item_write_offs",
        ["order_item_id"],
        unique=False,
    )
    op.drop_index(op.f("ix_write_offs_product_id"), table_name="write_offs")
    op.drop_index(op.f("ix_write_offs_org_id"), table_name="write_offs")
    op.drop_index(op.f("ix_write_offs_order_item_id"), table_name="write_offs")
    op.drop_table("write_offs")
