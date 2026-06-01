"""normalize existing user emails to lower case

Revision ID: a5b6c7d8e9f0
Revises: d5e6f7a8b9c0
Create Date: 2026-08-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "a5b6c7d8e9f0"
down_revision: str | Sequence[str] | None = "a4b5c6d7e8f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Detect case-only collisions (two accounts differing only by email case).
    # If any exist, the unique constraint would reject the lowercasing below;
    # surface them explicitly instead of failing mid-statement.
    collisions = op.get_bind().execute(
        text(
            """
            SELECT lower(email) AS norm, count(*) AS cnt
            FROM users
            GROUP BY lower(email)
            HAVING count(*) > 1
            """
        )
    )
    colliding = [row[0] for row in collisions]
    if colliding:
        raise RuntimeError(
            "Cannot normalize emails: case-only duplicates exist for: "
            + ", ".join(colliding)
        )

    op.execute(
        text("UPDATE users SET email = lower(email) WHERE email <> lower(email)")
    )


def downgrade() -> None:
    # Cannot reliably restore original casing; no-op.
    pass
