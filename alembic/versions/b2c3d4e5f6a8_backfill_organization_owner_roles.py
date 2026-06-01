"""backfill owner roles for existing organization memberships

Revision ID: b2c3d4e5f6a8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b2c3d4e5f6a8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE user_orgs AS membership
        SET role = 'owner'
        FROM organizations AS organization
        WHERE membership.org_id = organization.id
          AND membership.user_id = organization.owner_id
          AND membership.role <> 'owner'
        """
    )


def downgrade() -> None:
    # Existing memberships cannot be reliably distinguished from memberships
    # created after the backfill, so leave the corrected owner roles intact.
    pass
