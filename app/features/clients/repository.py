from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.clients.models import Client
from app.shared.exceptions import NotFoundException
from app.shared.filtering import (
    apply_sort,
    build_cursor_response,
    count_query,
    paginate_query,
)
from app.shared.sanitization import escape_like


class ClientRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, client: Client) -> Client:
        self.session.add(client)
        await self.session.flush()
        await self.session.refresh(client)

        return client

    async def get_by_ids(self, client_ids: Iterable[str | UUID]) -> list[Client]:
        ids = []

        for cid in client_ids:
            if not cid:
                continue

            if isinstance(cid, str):
                try:
                    cid = UUID(cid)
                except ValueError:
                    raise NotFoundException(f"Client not found: {cid}") from None

            ids.append(cid)

        if not ids:
            return []

        result = await self.session.execute(select(Client).where(Client.id.in_(ids)))

        return list(result.scalars().all())

    async def get_by_id(self, client_id: str | UUID) -> Client | None:
        if isinstance(client_id, str):
            try:
                client_id = UUID(client_id)
            except ValueError:
                raise NotFoundException(f"Client not found: {client_id}") from None

        result = await self.session.execute(
            select(Client).where(Client.id == client_id)
        )

        return result.scalar_one_or_none()

    async def get_by_id_and_org(
        self, client_id: str | UUID, org_id: str | UUID
    ) -> Client | None:
        if isinstance(client_id, str):
            try:
                client_id = UUID(client_id)
            except ValueError:
                raise NotFoundException(f"Client not found: {client_id}") from None

        if isinstance(org_id, str):
            try:
                org_id = UUID(org_id)
            except ValueError:
                raise NotFoundException(f"Organization not found: {org_id}") from None

        result = await self.session.execute(
            select(Client).where(Client.id == client_id, Client.org_id == org_id)
        )

        return result.scalar_one_or_none()

    async def get_by_org(
        self, org_id: str | UUID, include_archived: bool = False
    ) -> list[Client]:
        if isinstance(org_id, str):
            org_id = UUID(org_id)

        query = select(Client).where(Client.org_id == org_id)

        if not include_archived:
            query = query.where(Client.is_archived == False)  # noqa: E712

        query = query.order_by(Client.name)

        result = await self.session.execute(query)

        return list(result.scalars().all())

    async def get_by_phone(self, org_id: str | UUID, phone: str) -> Client | None:
        if isinstance(org_id, str):
            org_id = UUID(org_id)

        result = await self.session.execute(
            select(Client).where(
                Client.org_id == org_id,
                Client.phone == phone,
                # Deduplicate active clients only: an archive does not prevent
                # creating a new client with the same phone number.
                Client.is_archived == False,  # noqa: E712
            )
        )

        return result.scalar_one_or_none()

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
        if isinstance(org_id, str):
            org_id = UUID(org_id)

        query = select(Client).where(Client.org_id == org_id)

        if not include_archived:
            query = query.where(Client.is_archived == False)  # noqa: E712

        if name:
            query = query.where(
                Client.name.ilike(f"%{escape_like(name)}%", escape="\\")
            )

        if surname:
            query = query.where(
                Client.surname.ilike(f"%{escape_like(surname)}%", escape="\\")
            )

        if phone:
            query = query.where(
                Client.phone.ilike(f"%{escape_like(phone)}%", escape="\\")
            )

        if eav_filters:
            for code, value in eav_filters.items():
                query = query.where(Client.custom_fields[code].as_string() == value)

        total = await count_query(self.session, query)
        sort_map = {
            "name": Client.name,
            "phone": Client.phone,
            "created_at": Client.id,
        }
        query, sort_col, sort_desc = apply_sort(query, sort, sort_map, default="name")

        keyset = sort_col is not None and sort_col is not Client.id
        query, effective_limit = paginate_query(
            query,
            cursor,
            limit,
            id_column=Client.id,
            sort_column=sort_col if keyset else None,
            sort_desc=sort_desc,
        )
        result = await self.session.execute(query)
        items = list(result.scalars().all())
        sort_attr = sort_col.name if sort_col is not None and keyset else None
        items, next_cursor = build_cursor_response(
            items, effective_limit, sort_attr=sort_attr
        )

        return items, next_cursor, total
