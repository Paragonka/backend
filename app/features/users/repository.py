from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        # Case-insensitive lookup: emails stored with mixed casing must still
        # resolve to the same account (e.g. "Sovwva7@gmail.com" vs
        # "sovwva7@gmail.com"). The local part is normalized to lower case.
        result = await self.session.execute(
            select(User).where(func.lower(User.email) == email.strip().lower())
        )

        return result.scalar_one_or_none()

    async def get_by_ids(self, user_ids: Iterable[str | UUID]) -> list[User]:
        ids = [UUID(u) if isinstance(u, str) else u for u in user_ids if u]

        if not ids:
            return []

        result = await self.session.execute(select(User).where(User.id.in_(ids)))

        return list(result.scalars().all())

    async def get_by_id(self, user_id: str | UUID) -> User | None:
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        result = await self.session.execute(select(User).where(User.id == user_id))

        return result.scalar_one_or_none()

    async def add(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        await self.session.refresh(user)

        return user
