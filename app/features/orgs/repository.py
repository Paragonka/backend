from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.clients.models import Client
from app.features.eav.models import EavAttribute
from app.features.orders.models import Order, OrderItem, WriteOff
from app.features.orgs.models import (
    ROLE_MEMBER,
    Invite,
    Organization,
    OrganizationSetting,
    UserOrg,
)
from app.features.products.models import Product
from app.features.receipts.models import Receipt, ReceiptItem
from app.features.users.models import User


class OrgRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, org: Organization) -> Organization:
        self.session.add(org)
        await self.session.flush()
        await self.session.refresh(org)

        return org

    async def get_by_id(self, org_id: str | UUID) -> Organization | None:
        if isinstance(org_id, str):
            org_id = UUID(org_id)

        result = await self.session.execute(
            select(Organization).where(Organization.id == org_id)
        )

        return result.scalar_one_or_none()

    async def get_user_orgs(self, user_id: str | UUID) -> list[Organization]:
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        result = await self.session.execute(
            select(Organization).join(UserOrg).where(UserOrg.user_id == user_id)
        )

        return list(result.scalars().all())

    async def add_member(
        self,
        user_id: str | UUID,
        org_id: str | UUID,
        role: str = ROLE_MEMBER,
    ) -> UserOrg:
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        if isinstance(org_id, str):
            org_id = UUID(org_id)

        membership = UserOrg(user_id=user_id, org_id=org_id, role=role)
        self.session.add(membership)
        await self.session.flush()

        return membership

    async def get_membership(
        self, user_id: str | UUID, org_id: str | UUID
    ) -> UserOrg | None:
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        if isinstance(org_id, str):
            org_id = UUID(org_id)

        result = await self.session.execute(
            select(UserOrg).where(UserOrg.user_id == user_id, UserOrg.org_id == org_id)
        )

        return result.scalar_one_or_none()

    async def get_members_with_users(
        self, org_id: str | UUID
    ) -> list[tuple[UserOrg, User]]:
        if isinstance(org_id, str):
            org_id = UUID(org_id)

        result = await self.session.execute(
            select(UserOrg, User)
            .join(User, UserOrg.user_id == User.id)
            .where(UserOrg.org_id == org_id)
            .order_by(User.email)
        )

        return [(row[0], row[1]) for row in result.all()]

    async def remove_member(self, user_id: str | UUID, org_id: str | UUID) -> bool:
        if isinstance(user_id, str):
            user_id = UUID(user_id)

        if isinstance(org_id, str):
            org_id = UUID(org_id)

        result = cast(
            CursorResult,
            await self.session.execute(
                delete(UserOrg).where(
                    UserOrg.user_id == user_id, UserOrg.org_id == org_id
                )
            ),
        )

        return result.rowcount > 0

    async def count_owners(self, org_id: str | UUID) -> int:
        if isinstance(org_id, str):
            org_id = UUID(org_id)

        result = await self.session.execute(
            select(func.count())
            .select_from(UserOrg)
            .where(UserOrg.org_id == org_id, UserOrg.role == "owner")
        )

        return int(result.scalar_one())

    async def get_settings(self, org_id: str | UUID) -> dict[str, str]:
        if isinstance(org_id, str):
            org_id = UUID(org_id)

        result = await self.session.execute(
            select(OrganizationSetting).where(OrganizationSetting.org_id == org_id)
        )
        rows = result.scalars().all()

        return {s.key: s.value for s in rows}

    async def upsert_setting(self, org_id: str | UUID, key: str, value: str) -> None:
        if isinstance(org_id, str):
            org_id = UUID(org_id)

        existing = await self.session.execute(
            select(OrganizationSetting).where(
                OrganizationSetting.org_id == org_id,
                OrganizationSetting.key == key,
            )
        )
        setting = existing.scalar_one_or_none()

        if setting:
            setting.value = value
        else:
            self.session.add(
                OrganizationSetting(org_id=str(org_id), key=key, value=value)
            )

        await self.session.flush()

    async def delete_org(self, org_id: str | UUID) -> None:
        """Hard-delete an organization and all of its data.

        Order matters: child rows referencing products/clients must go first
        (FKs are RESTRICT/SET NULL, not CASCADE from organizations).
        """

        if isinstance(org_id, str):
            org_id = UUID(org_id)

        await self.session.execute(delete(Invite).where(Invite.org_id == org_id))
        await self.session.execute(delete(UserOrg).where(UserOrg.org_id == org_id))
        await self.session.execute(
            delete(OrganizationSetting).where(OrganizationSetting.org_id == org_id)
        )

        await self.session.execute(delete(WriteOff).where(WriteOff.org_id == org_id))
        order_ids = select(Order.id).where(Order.org_id == org_id)
        await self.session.execute(
            delete(OrderItem).where(OrderItem.order_id.in_(order_ids))
        )
        await self.session.execute(delete(Order).where(Order.org_id == org_id))
        receipt_ids = select(Receipt.id).where(Receipt.org_id == org_id)
        await self.session.execute(
            delete(ReceiptItem).where(ReceiptItem.receipt_id.in_(receipt_ids))
        )
        await self.session.execute(delete(Receipt).where(Receipt.org_id == org_id))

        await self.session.execute(
            delete(EavAttribute).where(EavAttribute.org_id == org_id)
        )
        await self.session.execute(delete(Client).where(Client.org_id == org_id))
        await self.session.execute(delete(Product).where(Product.org_id == org_id))

        await self.session.execute(
            delete(Organization).where(Organization.id == org_id)
        )
        await self.session.flush()


class InviteRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, invite: Invite) -> Invite:
        self.session.add(invite)
        await self.session.flush()
        await self.session.refresh(invite)

        return invite

    async def get_by_token(self, token: str) -> Invite | None:
        result = await self.session.execute(select(Invite).where(Invite.token == token))

        return result.scalar_one_or_none()

    async def get_active_by_org(self, org_id: str | UUID) -> list[Invite]:
        if isinstance(org_id, str):
            org_id = UUID(org_id)

        from datetime import UTC, datetime

        result = await self.session.execute(
            select(Invite)
            .where(
                Invite.org_id == org_id,
                Invite.used_at.is_(None),
                (Invite.expires_at.is_(None)) | (Invite.expires_at > datetime.now(UTC)),
            )
            .order_by(Invite.created_at.desc())
        )

        return list(result.scalars().all())

    async def get_by_org_and_email(
        self, org_id: str | UUID, email: str
    ) -> Invite | None:
        """Look up an invite in any state (used/expired/active) for (org, email)."""

        if isinstance(org_id, str):
            org_id = UUID(org_id)

        result = await self.session.execute(
            select(Invite)
            .where(Invite.org_id == org_id, Invite.email == email)
            .order_by(Invite.used_at.asc().nulls_first(), Invite.created_at.desc())
            .limit(1)
        )

        return result.scalars().first()

    async def get_by_id_and_org(
        self, invite_id: str | UUID, org_id: str | UUID
    ) -> Invite | None:
        if isinstance(invite_id, str):
            try:
                invite_id = UUID(invite_id)
            except ValueError:
                return None
        elif not isinstance(invite_id, UUID):
            return None

        if isinstance(org_id, str):
            org_id = UUID(org_id)

        result = await self.session.execute(
            select(Invite).where(Invite.id == invite_id, Invite.org_id == org_id)
        )

        return result.scalar_one_or_none()

    async def delete(self, invite: Invite) -> None:
        await self.session.delete(invite)
        await self.session.flush()

    async def mark_used(self, invite: Invite) -> Invite:
        from datetime import UTC, datetime

        invite.used_at = datetime.now(UTC)
        await self.session.flush()

        return invite
