from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.models import RefreshSession


class RefreshSessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_token_hash(self, token_hash: str) -> RefreshSession | None:
        result = await self.session.execute(
            select(RefreshSession).where(RefreshSession.token_hash == token_hash)
        )

        return result.scalar_one_or_none()

    async def get_by_id(self, session_id: str | UUID) -> RefreshSession | None:
        if isinstance(session_id, str):
            session_id = UUID(session_id)

        result = await self.session.execute(
            select(RefreshSession).where(RefreshSession.id == session_id)
        )

        return result.scalar_one_or_none()

    async def list_active_for_user(self, user_id: str | UUID) -> list[RefreshSession]:
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        result = await self.session.execute(
            select(RefreshSession)
            .where(
                RefreshSession.user_id == user_id,
                RefreshSession.revoked_at.is_(None),
            )
            .order_by(RefreshSession.created_at.desc())
        )

        return list(result.scalars().all())

    async def revoke(self, session_id: str | UUID) -> bool:
        """Mark a session revoked. Returns True if this call did the revoke.

        The WHERE revoked_at IS NULL guard makes concurrent rotations safe:
        the first caller wins, the second gets rowcount 0 and treats the
        token as reused.
        """
        if isinstance(session_id, str):
            session_id = UUID(session_id)

        result = cast(
            CursorResult,
            await self.session.execute(
                update(RefreshSession)
                .where(
                    RefreshSession.id == session_id,
                    RefreshSession.revoked_at.is_(None),
                )
                .values(revoked_at=datetime.now(UTC))
            ),
        )

        return result.rowcount > 0

    async def revoke_all_for_user(self, user_id: str | UUID) -> None:
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        await self.session.execute(
            update(RefreshSession)
            .where(
                RefreshSession.user_id == user_id,
                RefreshSession.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )

    async def add(self, session: RefreshSession) -> RefreshSession:
        self.session.add(session)
        await self.session.flush()
        await self.session.refresh(session)

        return session

    async def delete_by_token_hash(self, token_hash: str) -> bool:
        """Physically remove a session (used on logout) so its reuse is treated as
        'unknown session' instead of a rotation-reuse theft signal."""
        from sqlalchemy import delete

        result = cast(
            CursorResult,
            await self.session.execute(
                delete(RefreshSession).where(RefreshSession.token_hash == token_hash)
            ),
        )

        return result.rowcount > 0
