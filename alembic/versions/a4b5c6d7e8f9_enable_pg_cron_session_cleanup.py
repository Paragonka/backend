"""enable pg_cron and schedule refresh session cleanup

Revision ID: a4b5c6d7e8f9
Revises: d1e2f3a4b5c6
Create Date: 2026-08-28 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4b5c6d7e8f9"
down_revision: str | Sequence[str] | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JOB_NAME = "purge-refresh-sessions"
# Every hour, physically delete sessions whose refresh token can no longer be
# used (expired). Revoked-but-unexpired rows are intentionally KEPT: they power
# refresh-token reuse detection in AuthService.refresh_tokens, and any revoked
# row is cleaned automatically once its expires_at passes (<= refresh TTL).
_SCHEDULE = "0 * * * *"
_PURGE_SQL = "DELETE FROM refresh_sessions WHERE expires_at < now()"


def upgrade() -> None:
    """Upgrade schema."""
    # Requires the db image with pg_cron preloaded (shared_preload_libraries);
    # see db/Dockerfile and docker-compose db service command.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_cron;")
    # Idempotent: drop any pre-existing job with this name, then (re)create it.
    op.execute(
        sa.text(
            "SELECT cron.unschedule(:job) "
            "WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = :job)"
        ).bindparams(job=_JOB_NAME)
    )
    op.execute(
        sa.text("SELECT cron.schedule(:job, :schedule, :command)").bindparams(
            job=_JOB_NAME, schedule=_SCHEDULE, command=_PURGE_SQL
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.text("SELECT cron.unschedule(:job)").bindparams(job=_JOB_NAME))
    op.execute("DROP EXTENSION IF EXISTS pg_cron;")
