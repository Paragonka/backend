import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError

from app.core.log import get_logger
from app.core.uow import AppUnitOfWork
from app.features.orgs.models import (
    ORG_DEFAULT_SETTINGS,
    ROLE_MEMBER,
    ROLE_OWNER,
    Invite,
    Organization,
    UserOrg,
)
from app.features.orgs.repository import OrgRepository
from app.shared.exceptions import (
    ConflictException,
    ForbiddenException,
    GoneException,
    NotFoundException,
    ValidationException,
)

logger = get_logger(__name__)

INVITE_TTL_DAYS = 7


class OrgService:
    def __init__(self, uow: AppUnitOfWork):
        self.uow = uow

    @property
    def _orgs(self) -> OrgRepository:
        return OrgRepository(self.uow.session)

    async def create_org(
        self, name: str, owner_id: str, timezone: str = "UTC"
    ) -> Organization:
        async with self.uow:
            org = Organization(name=name, owner_id=owner_id, timezone=timezone)
            org = await self._orgs.add(org)
            await self._orgs.add_member(owner_id, str(org.id), role=ROLE_OWNER)

            for key, value in ORG_DEFAULT_SETTINGS.items():
                await self._orgs.upsert_setting(str(org.id), key, value)

            logger.info(
                "org_created", org_id=str(org.id), owner_id=str(owner_id), name=name
            )

            return org

    async def get_user_orgs(self, user_id: str) -> list[Organization]:
        async with self.uow:
            return await self._orgs.get_user_orgs(user_id)

    async def get_org(self, org_id: str) -> Organization | None:
        return await self._orgs.get_by_id(org_id)

    async def get_dashboard(self, org_id: str) -> dict:
        from app.features.clients.repository import ClientRepository
        from app.features.orders.repository import OrderRepository
        from app.features.products.repository import ProductRepository

        org = await self._orgs.get_by_id(org_id)

        today = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        order_repo = OrderRepository(self.uow.session)
        today_orders = await order_repo.get_by_date_range(org_id, today, today)
        week_orders = await order_repo.get_by_date_range(org_id, week_ago, today)

        orders_today_count = len(today_orders)
        orders_today_total = sum(o.total for o in today_orders)
        orders_week_count = len(week_orders)
        orders_week_total = sum(o.total for o in week_orders)

        client_repo = ClientRepository(self.uow.session)
        clients = await client_repo.get_by_org(org_id)
        client_count = len(clients)

        product_repo = ProductRepository(self.uow.session)
        products = await product_repo.get_by_org(org_id)
        product_count = len(products)

        recent_orders = []
        recent = await order_repo.get_recent(org_id, 5)
        client_ids = [o.client_id for o in recent if o.client_id]

        if client_ids:
            clients_by_id = {
                str(c.id): f"{c.name} {c.surname}"
                for c in await client_repo.get_by_ids(client_ids)
            }
        else:
            clients_by_id = {}

        for o in recent:
            recent_orders.append(
                {
                    "id": o.id,
                    "client_name": clients_by_id.get(str(o.client_id), ""),
                    "status": o.status,
                    "total": o.total,
                    "execution_date": o.execution_date,
                }
            )

        return {
            "org": org,
            "org_id": org_id,
            "orders_today_count": orders_today_count,
            "orders_today_total": orders_today_total,
            "orders_week_count": orders_week_count,
            "orders_week_total": orders_week_total,
            "client_count": client_count,
            "product_count": product_count,
            "recent_orders": recent_orders,
        }

    async def update_org(self, org_id: str, name: str) -> Organization:
        async with self.uow:
            org = await self._orgs.get_by_id(org_id)

            if not org:
                raise NotFoundException("Organization not found")

            org.name = name
            await self.uow.session.flush()

            logger.info("org_updated", org_id=org_id, name=name)

            return org

    async def delete_org(self, org_id: str) -> None:
        async with self.uow:
            org = await self._orgs.get_by_id(org_id)

            if not org:
                raise NotFoundException("Organization not found")

            await self._orgs.delete_org(org_id)
            logger.warning("org_deleted", org_id=org_id)

    async def list_members(self, org_id: str) -> list[dict]:
        async with self.uow:
            org = await self._orgs.get_by_id(org_id)
            owner_id = str(org.owner_id) if org else None
            rows = await self._orgs.get_members_with_users(org_id)

            return [
                {
                    "user_id": membership.user_id,
                    "email": user.email,
                    "full_name": user.full_name,
                    # Keep the API role in sync with the canonical owner_id
                    # for organizations created before UserOrg.role existed.
                    "role": (
                        ROLE_OWNER
                        if str(membership.user_id) == owner_id
                        else membership.role
                    ),
                }
                for membership, user in rows
            ]

    async def remove_member(
        self, org_id: str, target_user_id: str, acting_user_id: str
    ) -> None:
        async with self.uow:
            if target_user_id == acting_user_id:
                raise ForbiddenException("Cannot remove yourself from organization")

            try:
                membership = await self._orgs.get_membership(target_user_id, org_id)
            except ValueError:
                raise ValidationException(
                    f"Invalid user ID format: {target_user_id}"
                ) from None

            if not membership:
                raise NotFoundException("Member not found in this organization")

            if membership.role == ROLE_OWNER:
                owners = await self._orgs.count_owners(org_id)

                if owners <= 1:
                    raise ConflictException("Cannot remove the last owner")

            await self._orgs.remove_member(target_user_id, org_id)
            logger.info(
                "org_member_removed",
                org_id=org_id,
                target_user_id=target_user_id,
                acting_user_id=acting_user_id,
            )

    async def get_settings(self, org_id: str) -> dict:
        async with self.uow:
            stored = await self._orgs.get_settings(org_id)

            return {**ORG_DEFAULT_SETTINGS, **stored}

    async def update_settings(self, org_id: str, settings: dict) -> dict:
        async with self.uow:
            stored = await self._orgs.get_settings(org_id)
            merged = {**ORG_DEFAULT_SETTINGS, **stored, **settings}

            for key, value in merged.items():
                await self._orgs.upsert_setting(org_id, key, value)

            logger.info(
                "org_settings_updated", org_id=org_id, keys=list(settings.keys())
            )

            return merged


class InviteService:
    def __init__(self, uow: AppUnitOfWork):
        self.uow = uow

    @property
    def _invites(self):
        return self.uow.invites

    @property
    def _orgs(self) -> OrgRepository:
        return OrgRepository(self.uow.session)

    async def create_invite(self, org_id: str, email: str, created_by: str) -> Invite:
        async with self.uow:
            active = await self._invites.get_active_by_org(org_id)

            if any(i.email == email.lower() for i in active):
                raise ConflictException(f"Active invite already exists for {email}")

            invite = Invite(
                org_id=org_id,
                email=email.lower(),
                token=secrets.token_urlsafe(32),
                expires_at=datetime.now(UTC) + timedelta(days=INVITE_TTL_DAYS),
                created_by=created_by,
            )

            try:
                invite = await self._invites.add(invite)
            except IntegrityError:
                # uq_invites_org_email_active (used_at IS NULL, no expires_at
                # check) also blocks invites that expired: clear the expired
                # one and retry the INSERT once.
                await self.uow.session.rollback()

                existing = await self._invites.get_by_org_and_email(
                    org_id, email.lower()
                )

                if existing is None or existing.used_at is not None:
                    raise ConflictException(
                        f"Active invite already exists for {email}"
                    ) from None

                expires_at = existing.expires_at

                if expires_at is None:
                    raise ConflictException(
                        f"Active invite already exists for {email}"
                    ) from None

                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)

                if expires_at >= datetime.now(UTC):
                    raise ConflictException(
                        f"Active invite already exists for {email}"
                    ) from None

                await self._invites.delete(existing)
                invite = Invite(
                    org_id=org_id,
                    email=email.lower(),
                    token=secrets.token_urlsafe(32),
                    expires_at=datetime.now(UTC) + timedelta(days=INVITE_TTL_DAYS),
                    created_by=created_by,
                )

                try:
                    invite = await self._invites.add(invite)
                except IntegrityError as e:
                    # Concurrent request re-created the invite in between.
                    raise ConflictException(
                        f"Active invite already exists for {email}"
                    ) from e
            logger.info(
                "invite_created",
                org_id=org_id,
                email=email.lower(),
                created_by=created_by,
            )
            return invite

    async def list_active_invites(self, org_id: str) -> list[Invite]:
        async with self.uow:
            return await self._invites.get_active_by_org(org_id)

    async def revoke_invite(self, invite_id: str, org_id: str) -> bool:
        async with self.uow:
            invite = await self._invites.get_by_id_and_org(invite_id, org_id)

            if not invite:
                return False

            await self._invites.delete(invite)

            logger.info("invite_revoked", invite_id=invite_id, org_id=org_id)

            return True

    async def accept_invite(
        self, token: str, user_id: str
    ) -> tuple[Organization, UserOrg]:
        async with self.uow:
            invite = await self._invites.get_by_token(token)

            if not invite:
                raise NotFoundException("Invalid invite token")

            if invite.used_at is not None:
                raise ConflictException("Invite has already been used")

            expires_at = invite.expires_at

            if expires_at is not None:
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=UTC)

                if expires_at < datetime.now(UTC):
                    raise GoneException("Invite has expired")

            user = await self.uow.users.get_by_id(user_id)

            if not user or user.email.lower() != invite.email.lower():
                raise ForbiddenException(
                    "This invitation was sent to a different email address"
                )

            existing = await self._orgs.get_membership(user_id, invite.org_id)

            if existing:
                raise ConflictException("User is already a member of this organization")

            try:
                membership = await self._orgs.add_member(
                    user_id, invite.org_id, role=ROLE_MEMBER
                )
            except IntegrityError as e:
                # PK (user_id, org_id): a concurrent accept already added the
                # user to this organization.
                raise ConflictException(
                    "User is already a member of this organization"
                ) from e
            await self._invites.mark_used(invite)

            org = await self._orgs.get_by_id(invite.org_id)

            if not org:
                raise NotFoundException("Organization not found")

            logger.info(
                "invite_accepted",
                org_id=str(invite.org_id),
                user_id=user_id,
                email=invite.email,
            )

            return org, membership
