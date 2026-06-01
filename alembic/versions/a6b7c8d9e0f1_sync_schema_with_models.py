"""sync schema with ORM models and add missing uniqueness invariants

Revision ID: a6b7c8d9e0f1
Revises: a5b6c7d8e9f0
Create Date: 2026-08-28

Drops audit columns (created_by/updated_by) from clients, products and
receipts - they exist in the DB but the ORM models no longer declare them
(only orders keeps the audit trail). Also adds the indexes the models
declare, removes a redundant duplicate unique constraint on
refresh_sessions.token_hash, and adds DB-level uniqueness for business
invariants previously enforced only by racy application checks.

Existing data may contain duplicates of these new keys (created by the old
check-then-insert upsert paths). The migration deduplicates conservatively:
clients -> older duplicates archived, products -> older duplicates renamed,
invites -> older duplicates revoked. No rows are deleted.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "a6b7c8d9e0f1"
down_revision: str | Sequence[str] | None = "a5b6c7d8e9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUDITED_TABLES = ("clients", "products", "receipts")


def upgrade() -> None:
    # Drop dead audit columns from tables whose models no longer declare them.
    for table in _AUDITED_TABLES:
        op.drop_index(f"ix_{table}_created_by", table_name=table)
        op.drop_constraint(f"{table}_created_by_fkey", table, type_="foreignkey")
        op.drop_constraint(f"{table}_updated_by_fkey", table, type_="foreignkey")
        op.drop_column(table, "created_by")
        op.drop_column(table, "updated_by")

    # Index the model declares (Order.updated_by index=True) but the DB lacks.
    op.create_index("ix_orders_updated_by", "orders", ["updated_by"])

    # token_hash is already covered by the unique index
    # ix_refresh_sessions_token_hash; the duplicate named constraint adds no
    # protection and makes the schema drift from the ORM model.
    op.drop_constraint(
        "refresh_sessions_token_hash_key", "refresh_sessions", type_="unique"
    )

    # --- Deduplicate existing data before adding unique indexes ------------

    # clients: archive every active duplicate except the newest per
    # (org_id, phone) for non-empty phones.
    op.execute(
        text(
            """
            WITH ranked AS (
                SELECT id,
                       row_number() OVER (
                           PARTITION BY org_id, phone
                           ORDER BY created_at DESC, id DESC
                       ) AS rn
                FROM clients
                WHERE phone <> '' AND is_archived = false
            )
            UPDATE clients c
            SET is_archived = true
            FROM ranked
            WHERE c.id = ranked.id AND ranked.rn > 1
            """
        )
    )

    # products: rename every duplicate except the newest per (org_id, name, unit).
    op.execute(
        text(
            """
            WITH ranked AS (
                SELECT id,
                       row_number() OVER (
                           PARTITION BY org_id, name, unit
                           ORDER BY created_at DESC, id DESC
                       ) AS rn
                FROM products
            )
            UPDATE products p
            SET name = substring(p.name, 1, 240) || ' (' || substring(p.id::text, 1, 8) || ')'
            FROM ranked
            WHERE p.id = ranked.id AND ranked.rn > 1
            """
        )
    )

    # invites: revoke every active duplicate except the newest per (org_id, email).
    op.execute(
        text(
            """
            WITH ranked AS (
                SELECT id,
                       row_number() OVER (
                           PARTITION BY org_id, email
                           ORDER BY created_at DESC, id DESC
                       ) AS rn
                FROM invites
                WHERE used_at IS NULL
            )
            UPDATE invites i
            SET used_at = now()
            FROM ranked
            WHERE i.id = ranked.id AND ranked.rn > 1
            """
        )
    )

    # --- Unique invariants at the DB level --------------------------------

    # write_offs: duplicate rows per order_item were produced by the old
    # double-write-off bug (each duplicate also decremented stock). Keep the
    # first write-off per item and remove the later duplicates.
    op.execute(
        text(
            """
            DELETE FROM write_offs
            WHERE id IN (
                SELECT id
                FROM (
                    SELECT id,
                           row_number() OVER (
                               PARTITION BY order_item_id
                               ORDER BY created_at, id
                           ) AS rn
                    FROM write_offs
                    WHERE order_item_id IS NOT NULL
                ) ranked
                WHERE ranked.rn > 1
            )
            """
        )
    )

    # At most one write-off per order item (prevents double stock spending).
    op.create_index(
        "uq_write_offs_order_item",
        "write_offs",
        ["order_item_id"],
        unique=True,
        postgresql_where=text("order_item_id IS NOT NULL"),
    )

    # One active client per (org, phone): upsert deduplicates on phone.
    op.create_index(
        "uq_clients_org_phone_active",
        "clients",
        ["org_id", "phone"],
        unique=True,
        postgresql_where=text("phone <> '' AND is_archived = false"),
    )

    # One product per (org, name, unit): upsert deduplicates on (name, unit).
    op.create_index(
        "uq_products_org_name_unit",
        "products",
        ["org_id", "name", "unit"],
        unique=True,
    )

    # One active invite per (org, email): used invites are not counted.
    op.create_index(
        "uq_invites_org_email_active",
        "invites",
        ["org_id", "email"],
        unique=True,
        postgresql_where=text("used_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_invites_org_email_active", table_name="invites")
    op.drop_index("uq_products_org_name_unit", table_name="products")
    op.drop_index("uq_clients_org_phone_active", table_name="clients")
    op.drop_index("uq_write_offs_order_item", table_name="write_offs")

    op.create_unique_constraint(
        "refresh_sessions_token_hash_key", "refresh_sessions", ["token_hash"]
    )

    op.drop_index("ix_orders_updated_by", table_name="orders")

    for table in reversed(_AUDITED_TABLES):
        op.add_column(
            table,
            sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        )
        op.create_index(f"ix_{table}_created_by", table, ["created_by"])
