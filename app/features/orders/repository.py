from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.clients.models import Client
from app.features.orders.models import Order, OrderItem, WriteOff
from app.shared.exceptions import NotFoundException
from app.shared.filtering import (
    apply_sort,
    build_cursor_response,
    count_query,
    paginate_query,
)


def _to_uuid(value: str | UUID, message: str) -> UUID:
    if isinstance(value, UUID):
        return value

    try:
        return UUID(value)
    except ValueError:
        raise NotFoundException(f"{message}: {value}") from None


class OrderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, order: Order) -> Order:
        self.session.add(order)
        await self.session.flush()
        await self.session.refresh(order)

        return order

    async def get_by_id(self, order_id: str | UUID) -> Order | None:
        order_id = _to_uuid(order_id, "Order not found")
        result = await self.session.execute(select(Order).where(Order.id == order_id))

        return result.scalar_one_or_none()

    async def get_by_id_and_org(
        self, order_id: str | UUID, org_id: str | UUID
    ) -> Order | None:
        order_id = _to_uuid(order_id, "Order not found")

        if isinstance(org_id, str):
            try:
                org_id = UUID(org_id)
            except ValueError:
                raise NotFoundException(f"Organization not found: {org_id}") from None

        result = await self.session.execute(
            select(Order).where(Order.id == order_id, Order.org_id == org_id)
        )

        return result.scalar_one_or_none()

    async def get_by_org(
        self, org_id: str | UUID, include_deleted: bool = False
    ) -> list[Order]:
        if isinstance(org_id, str):
            org_id = UUID(org_id)

        query = select(Order).where(Order.org_id == org_id)

        if not include_deleted:
            query = query.where(Order.is_deleted == False)  # noqa: E712

        query = query.order_by(Order.created_at.desc())
        result = await self.session.execute(query)

        return list(result.scalars().all())

    # C901: filters + sorting + keyset pagination in one query;
    # splitting it would complicate the code without benefit
    async def get_filtered(  # noqa: C901
        self,
        org_id: str | UUID,
        cursor: str | None = None,
        limit: int = 50,
        status: str | None = None,
        execution_date_from: str | None = None,
        execution_date_to: str | None = None,
        created_from: str | None = None,
        created_to: str | None = None,
        sort: str | None = None,
        include_deleted: bool = False,
    ) -> tuple[
        list[Order],
        str | None,
        int,
        dict[UUID, str],
        dict[UUID, list[OrderItem]],
    ]:
        """Returns (orders, next_cursor, total, client_names_map, items_by_order_map).

        client_names_map: order.client_id -> client.name (empty string if no client).
        items_by_order_map: order.id -> list of OrderItem objects.
        """

        if isinstance(org_id, str):
            org_id = UUID(org_id)

        # ── filters ───────────────────────────────────────────────────────────
        query = (
            select(Order, Client.name.label("client_name"))
            .outerjoin(Client, Order.client_id == Client.id)
            .where(Order.org_id == org_id)
        )

        if not include_deleted:
            query = query.where(Order.is_deleted == False)  # noqa: E712

        if status:
            query = query.where(Order.status == status)

        if execution_date_from:
            query = query.where(Order.execution_date >= execution_date_from)

        if execution_date_to:
            query = query.where(Order.execution_date <= execution_date_to)

        if created_from:
            query = query.where(sa_func.date(Order.created_at) >= created_from)

        if created_to:
            query = query.where(sa_func.date(Order.created_at) <= created_to)

        total = await count_query(self.session, query)

        # ── sort ──────────────────────────────────────────────────────────────
        sort_map = {
            "execution_date": Order.execution_date,
            "total": Order.total,
            "created_at": Order.id,
            "status": Order.status,
        }
        query, sort_col, sort_desc = apply_sort(
            query, sort, sort_map, default="-created_at"
        )
        keyset = sort_col is not None and sort_col is not Order.id
        query, effective_limit = paginate_query(
            query,
            cursor,
            limit,
            id_column=Order.id,
            sort_column=sort_col if keyset else None,
            sort_desc=sort_desc,
        )

        # ── execute ───────────────────────────────────────────────────────────
        result = await self.session.execute(query)
        rows = list(result.all())

        # Unpack (Order, client_name) tuples
        orders = [r[0] for r in rows]
        client_names: dict[UUID, str] = {}

        for order, cname in rows:
            client_names[order.id] = cname or ""

        # cursor paginate on the order list
        sort_attr = (
            sort_col.name
            if (sort_col is not None and sort_col is not Order.id)
            else None
        )
        orders, next_cursor = build_cursor_response(
            orders,
            effective_limit,
            sort_attr=sort_attr,
        )

        # ── bulk-fetch order items for this page ──────────────────────────────
        items_map: dict[UUID, list[OrderItem]] = {o.id: [] for o in orders}

        if orders:
            order_ids = [o.id for o in orders]
            result = await self.session.execute(
                select(OrderItem).where(OrderItem.order_id.in_(order_ids))
            )

            for item in result.scalars().all():
                items_map[item.order_id].append(item)

        return orders, next_cursor, total, client_names, items_map

    async def get_recent(self, org_id: str | UUID, limit: int = 5) -> list[Order]:
        """Bounded recent-orders fetch (avoids loading the whole table)."""

        if isinstance(org_id, str):
            org_id = UUID(org_id)

        query = (
            select(Order)
            .where(Order.org_id == org_id, Order.is_deleted == False)  # noqa: E712
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(query)

        return list(result.scalars().all())

    async def get_by_org_and_client(
        self, org_id: str | UUID, client_id: str | UUID
    ) -> list[Order]:
        """One client's orders within an organization (no full org load)."""

        if isinstance(org_id, str):
            org_id = UUID(org_id)

        if isinstance(client_id, str):
            client_id = UUID(client_id)

        query = (
            select(Order)
            .where(Order.org_id == org_id, Order.client_id == client_id)
            .order_by(Order.created_at.desc())
        )
        result = await self.session.execute(query)

        return list(result.scalars().all())

    async def get_by_date_range(
        self,
        org_id: str | UUID,
        date_from: str,
        date_to: str,
        include_deleted: bool = False,
    ) -> list[Order]:
        if isinstance(org_id, str):
            org_id = UUID(org_id)

        end_exclusive = (
            datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
        ).strftime("%Y-%m-%d")

        query = (
            select(Order)
            .where(Order.org_id == org_id)
            .where(Order.execution_date >= date_from)
            .where(Order.execution_date < end_exclusive)
        )

        if not include_deleted:
            query = query.where(Order.is_deleted == False)  # noqa: E712

        query = query.order_by(Order.execution_date, Order.id)
        result = await self.session.execute(query)

        return list(result.scalars().all())

    async def delete(self, order: Order) -> None:
        await self.session.delete(order)
        await self.session.flush()


class OrderItemRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, item: OrderItem) -> OrderItem:
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)

        return item

    async def get_by_id(self, item_id: str | UUID) -> OrderItem | None:
        item_id = _to_uuid(item_id, "Item not found")
        result = await self.session.execute(
            select(OrderItem).where(OrderItem.id == item_id)
        )

        return result.scalar_one_or_none()

    async def get_by_order(self, order_id: str | UUID) -> list[OrderItem]:
        order_id = _to_uuid(order_id, "Order not found")
        result = await self.session.execute(
            select(OrderItem).where(OrderItem.order_id == order_id)
        )

        return list(result.scalars().all())

    async def get_items_map_for_orders(
        self, order_ids: list[UUID]
    ) -> dict[UUID, list[OrderItem]]:
        """Items for multiple orders in one query (bulk, as in get_filtered)."""
        items_map: dict[UUID, list[OrderItem]] = {oid: [] for oid in order_ids}

        if not order_ids:
            return items_map

        result = await self.session.execute(
            select(OrderItem).where(OrderItem.order_id.in_(order_ids))
        )

        for item in result.scalars().all():
            items_map[item.order_id].append(item)

        return items_map

    async def delete(self, item: OrderItem) -> None:
        await self.session.delete(item)
        await self.session.flush()


class WriteOffRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, wo: WriteOff) -> WriteOff:
        self.session.add(wo)
        await self.session.flush()
        await self.session.refresh(wo)

        return wo

    async def get_by_order_item(self, order_item_id: str | UUID) -> list[WriteOff]:
        order_item_id = _to_uuid(order_item_id, "Write-off not found")
        result = await self.session.execute(
            select(WriteOff).where(WriteOff.order_item_id == order_item_id)
        )

        return list(result.scalars().all())
