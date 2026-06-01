from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.core.log import get_logger
from app.core.uow import AppUnitOfWork
from app.features.clients.models import Client
from app.features.clients.repository import ClientRepository
from app.features.eav.service import EavAttributeService
from app.shared.constants import ENTITY_TYPE_CLIENT
from app.shared.exceptions import ValidationException
from app.shared.sanitization import strip_html_tags

logger = get_logger(__name__)


class ClientService:
    def __init__(self, uow: AppUnitOfWork):
        self.uow = uow

    @property
    def _clients(self) -> ClientRepository:
        return ClientRepository(self.uow.session)

    async def create_client(
        self,
        org_id: str,
        name: str,
        surname: str = "",
        phone: str = "",
        notes: str = "",
        custom_fields: dict | None = None,
        local_fields: dict | None = None,
    ) -> Client:
        async with self.uow:
            if custom_fields:
                attrs = await self.uow.eav_attributes.get_by_entity_code(
                    org_id, ENTITY_TYPE_CLIENT
                )
                EavAttributeService.validate_custom_fields(custom_fields, attrs)

            client = Client(
                org_id=org_id,
                name=strip_html_tags(name),
                surname=strip_html_tags(surname),
                phone=phone,
                notes=strip_html_tags(notes),
                custom_fields=custom_fields or {},
                local_fields=local_fields or {},
            )

            client = await self._clients.add(client)
            logger.info("client_created", client_id=str(client.id), org_id=org_id)
            return client

    async def _apply_upsert_update(
        self,
        existing: Client,
        *,
        name: str,
        surname: str,
        phone: str,
        notes: str,
        custom_fields: dict | None,
        local_fields: dict | None,
    ) -> None:
        merged = {**existing.custom_fields, **(custom_fields or {})}

        if merged:
            attrs = await self.uow.eav_attributes.get_by_entity_code(
                existing.org_id, ENTITY_TYPE_CLIENT
            )
            EavAttributeService.validate_custom_fields(merged, attrs)

        if name:
            existing.name = strip_html_tags(name)

        if surname:
            existing.surname = strip_html_tags(surname)

        existing.phone = phone

        if notes:
            existing.notes = strip_html_tags(notes)

        if custom_fields is not None:
            existing.custom_fields = merged

        if local_fields is not None:
            existing.local_fields = {
                **existing.local_fields,
                **local_fields,
            }

        await self.uow.session.flush()
        await self.uow.session.refresh(existing)

    async def upsert_client(
        self,
        org_id: str,
        name: str,
        surname: str = "",
        phone: str = "",
        notes: str = "",
        custom_fields: dict | None = None,
        local_fields: dict | None = None,
    ) -> tuple[Client, str]:
        """Deduplicate by key: phone (non-empty).

        Returns (client, "created"|"updated").
        """

        async with self.uow:
            existing = (
                await self._clients.get_by_phone(org_id, phone) if phone else None
            )

            if existing:
                await self._apply_upsert_update(
                    existing,
                    name=name,
                    surname=surname,
                    phone=phone,
                    notes=notes,
                    custom_fields=custom_fields,
                    local_fields=local_fields,
                )
                logger.info("client_updated", client_id=str(existing.id), org_id=org_id)

                return existing, "updated"

            if custom_fields:
                attrs = await self.uow.eav_attributes.get_by_entity_code(
                    org_id, ENTITY_TYPE_CLIENT
                )
                EavAttributeService.validate_custom_fields(custom_fields, attrs)

            client = Client(
                org_id=org_id,
                name=strip_html_tags(name),
                surname=strip_html_tags(surname),
                phone=phone,
                notes=strip_html_tags(notes),
                custom_fields=custom_fields or {},
                local_fields=local_fields or {},
            )

            try:
                created = await self._clients.add(client)
            except IntegrityError:
                # Concurrent upsert with the same phone won the race
                # (uq_clients_org_phone_active). Fall back to the update path.
                await self.uow.session.rollback()

                if not phone:
                    raise

                existing = await self._clients.get_by_phone(org_id, phone)

                if not existing:
                    raise

                await self._apply_upsert_update(
                    existing,
                    name=name,
                    surname=surname,
                    phone=phone,
                    notes=notes,
                    custom_fields=custom_fields,
                    local_fields=local_fields,
                )

                return existing, "updated"

            logger.info("client_created", client_id=str(created.id), org_id=org_id)
            return created, "created"

    async def update_client_in_org(
        self, client_id: str | UUID, org_id: str | UUID, **fields
    ) -> Client | None:
        """Composite (org_id, id) lookup + mutation in one transaction.

        Closes the check-then-mutate race: a foreign/nonexistent client is
        never mutated. 404 semantics stay at the router level.
        """

        async with self.uow:
            client = await self._clients.get_by_id_and_org(client_id, org_id)

            if not client:
                return None

            await self._apply_fields(client, **fields)
            await self.uow.session.flush()
            await self.uow.session.refresh(client)

            logger.info("client_updated", client_id=str(client.id), org_id=org_id)
            return client

    async def _apply_fields(self, client: Client, **fields) -> None:
        custom_fields = fields.get("custom_fields")
        local_fields = fields.get("local_fields")

        if custom_fields is not None:
            attrs = await self.uow.eav_attributes.get_by_entity_code(
                client.org_id, ENTITY_TYPE_CLIENT
            )
            EavAttributeService.validate_custom_fields(custom_fields, attrs)
            client.custom_fields = custom_fields

        if local_fields is not None:
            client.local_fields = local_fields

        if fields.get("name") is not None:
            client.name = strip_html_tags(fields["name"])

        if fields.get("surname") is not None:
            client.surname = strip_html_tags(fields["surname"])

        if fields.get("phone") is not None:
            client.phone = fields["phone"]

        if fields.get("notes") is not None:
            client.notes = strip_html_tags(fields["notes"])

    async def get_client_in_org(
        self, client_id: str | UUID, org_id: str | UUID
    ) -> Client | None:
        """Composite lookup (org_id, id) - 404 semantics at the router level."""

        return await self._clients.get_by_id_and_org(client_id, org_id)

    async def get_client_visible(
        self,
        client_id: str | UUID,
        org_id: str | UUID,
        include_archived: bool = False,
    ) -> Client | None:
        """An archived client is indistinguishable from a deleted one.

        Composite lookup (org_id, id); an archived client is returned only
        when include_archived is set.
        """

        client = await self._clients.get_by_id_and_org(client_id, org_id)

        if not client:
            return None

        if client.is_archived and not include_archived:
            return None

        return client

    async def get_org_clients(
        self, org_id: str | UUID, include_archived: bool = False
    ) -> list[Client]:
        return await self._clients.get_by_org(org_id, include_archived=include_archived)

    async def get_filtered(
        self,
        org_id: str | UUID,
        cursor: str | None = None,
        limit: int = 50,
        name: str | None = None,
        surname: str | None = None,
        phone: str | None = None,
        eav_filters: dict[str, str] | None = None,
        sort: str | None = None,
        include_archived: bool = False,
    ) -> tuple[list[Client], str | None, int]:
        try:
            return await self._clients.get_filtered(
                org_id=org_id,
                cursor=cursor,
                limit=limit,
                name=name,
                surname=surname,
                phone=phone,
                eav_filters=eav_filters,
                sort=sort,
                include_archived=include_archived,
            )
        except ValueError as e:
            raise ValidationException(str(e)) from e

    async def archive_client(
        self, client_id: str | UUID, org_id: str | UUID
    ) -> Client | None:
        """Soft-delete - is_archived=True. Idempotent, with no hard DELETE."""

        async with self.uow:
            client = await self._clients.get_by_id_and_org(client_id, org_id)

            if not client:
                return None

            client.is_archived = True
            await self.uow.session.flush()
            await self.uow.session.refresh(client)

            logger.info("client_archived", client_id=str(client.id), org_id=org_id)
            return client

    async def restore_client(
        self, client_id: str | UUID, org_id: str | UUID
    ) -> Client | None:
        """Clear the archive flag (idempotent for a non-archived client)."""

        async with self.uow:
            client = await self._clients.get_by_id_and_org(client_id, org_id)

            if not client:
                return None

            client.is_archived = False
            await self.uow.session.flush()
            await self.uow.session.refresh(client)

            logger.info("client_restored", client_id=str(client.id), org_id=org_id)
            return client
