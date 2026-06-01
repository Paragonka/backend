from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.eav.models import EavAttribute
from app.shared.exceptions import NotFoundException


class EavAttributeRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, attribute: EavAttribute) -> EavAttribute:
        self.session.add(attribute)
        await self.session.flush()
        await self.session.refresh(attribute)

        return attribute

    async def get_by_id(self, attr_id: str | UUID) -> EavAttribute | None:
        if isinstance(attr_id, str):
            try:
                attr_id = UUID(attr_id)
            except ValueError:
                raise NotFoundException(f"Attribute not found: {attr_id}") from None

        result = await self.session.execute(
            select(EavAttribute).where(EavAttribute.id == attr_id)
        )

        return result.scalar_one_or_none()

    async def get_by_id_and_org(
        self, attr_id: str | UUID, org_id: str | UUID
    ) -> EavAttribute | None:
        if isinstance(attr_id, str):
            try:
                attr_id = UUID(attr_id)
            except ValueError:
                raise NotFoundException(f"Attribute not found: {attr_id}") from None

        if isinstance(org_id, str):
            org_id = UUID(org_id)

        result = await self.session.execute(
            select(EavAttribute).where(
                EavAttribute.id == attr_id, EavAttribute.org_id == org_id
            )
        )

        return result.scalar_one_or_none()

    async def get_by_code(
        self, org_id: str | UUID, entity_code: str, code: str
    ) -> EavAttribute | None:
        if isinstance(org_id, str):
            org_id = UUID(org_id)

        result = await self.session.execute(
            select(EavAttribute).where(
                and_(
                    EavAttribute.org_id == org_id,
                    EavAttribute.entity_code == entity_code,
                    EavAttribute.code == code,
                )
            )
        )

        return result.scalar_one_or_none()

    async def get_by_entity_code(
        self, org_id: str | UUID, entity_code: str
    ) -> list[EavAttribute]:
        if isinstance(org_id, str):
            org_id = UUID(org_id)

        result = await self.session.execute(
            select(EavAttribute).where(
                EavAttribute.org_id == org_id,
                EavAttribute.entity_code == entity_code,
            )
        )

        return list(result.scalars().all())

    async def get_all(self, org_id: str | UUID) -> list[EavAttribute]:
        if isinstance(org_id, str):
            org_id = UUID(org_id)

        result = await self.session.execute(
            select(EavAttribute).where(EavAttribute.org_id == org_id)
        )

        return list(result.scalars().all())

    async def delete(self, attribute: EavAttribute) -> None:
        await self.session.delete(attribute)
        await self.session.flush()
