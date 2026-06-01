from collections.abc import Iterable
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.core.log import get_logger
from app.core.uow import AppUnitOfWork
from app.features.clients.repository import ClientRepository
from app.features.eav.service import EavAttributeService
from app.features.orders.models import Order, OrderItem, WriteOff
from app.features.orders.repository import (
    OrderItemRepository,
    OrderRepository,
    WriteOffRepository,
)
from app.features.orders.schemas import (
    OrderItemCreate,
    OrderItemResponse,
    OrderResponse,
    validate_execution_date,
)
from app.features.products.repository import ProductRepository
from app.features.users.repository import UserRepository
from app.shared.constants import ENTITY_TYPE_ORDER
from app.shared.exceptions import (
    ConflictException,
    NotFoundException,
    StockError,
    ValidationException,
)

logger = get_logger(__name__)


def _as_uuid(value: str | UUID | None) -> UUID | None:
    if value is None or isinstance(value, UUID):
        return value

    return UUID(value)


class OrderService:
    def __init__(self, uow: AppUnitOfWork):
        self.uow = uow

    @property
    def _orders(self) -> OrderRepository:
        return OrderRepository(self.uow.session)

    @property
    def _items(self) -> OrderItemRepository:
        return OrderItemRepository(self.uow.session)

    @property
    def _writeoffs(self) -> WriteOffRepository:
        return WriteOffRepository(self.uow.session)

    @property
    def _products(self) -> ProductRepository:
        return ProductRepository(self.uow.session)

    async def create_order(
        self,
        org_id: str,
        client_id: str | UUID | None = None,
        execution_date: str = "",
        notes: str = "",
        local_fields: dict | None = None,
        custom_fields: dict | None = None,
        created_by: str | UUID | None = None,
        items: list[OrderItemCreate] | list[dict] | None = None,
    ) -> Order:
        # duplicate validation at the service level - web_router (HTMX forms)
        # calls the service directly, bypassing Pydantic schemas.
        try:
            validate_execution_date(execution_date)
        except ValueError as e:
            raise ValidationException(str(e)) from e

        async with self.uow:
            if custom_fields:
                attrs = await self.uow.eav_attributes.get_by_entity_code(
                    org_id, ENTITY_TYPE_ORDER
                )
                EavAttributeService.validate_custom_fields(custom_fields, attrs)

            if client_id is not None:
                try:
                    client = await ClientRepository(self.uow.session).get_by_id_and_org(
                        client_id, org_id
                    )
                except NotFoundException as e:
                    raise ValidationException("Client not found") from e

                if not client:
                    raise ValidationException("Client not found")

            order = Order(
                org_id=UUID(org_id),
                client_id=_as_uuid(client_id),
                execution_date=execution_date,
                notes=notes,
                local_fields=local_fields or {},
                custom_fields=custom_fields or {},
                created_by=_as_uuid(created_by),
            )

            order = await self._orders.add(order)

            if items:
                await self._add_items_with_stock(order, items, org_id)
                await self._recalc_total(order.id)

            logger.info(
                "order_created",
                order_id=str(order.id),
                org_id=org_id,
                client_id=str(client_id) if client_id else None,
                item_count=len(items) if items else 0,
                created_by=str(created_by) if created_by else None,
            )

            return order

    async def _add_items_with_stock(
        self,
        order: Order,
        items: Iterable[OrderItemCreate | dict],
        org_id: str,
    ) -> None:
        for item_data in items:
            if isinstance(item_data, OrderItemCreate):
                product_id = item_data.product_id
                name = item_data.name
                price = item_data.price
                qty = item_data.qty
            else:
                product_id = item_data.get("product_id") or None
                name = item_data.get("name", "")
                price = item_data.get("price", 0)
                qty = item_data.get("qty", 1)

            order_item = OrderItem(
                order_id=order.id,
                product_id=product_id,
                name=name,
                price=price,
                qty=qty,
            )
            order_item = await self._items.add(order_item)

            if not product_id:
                continue

            product = await self._products.get_by_id_and_org(product_id, org_id)

            if not product:
                raise ValidationException(f"Product not found: {product_id}")

            if product.track_inventory and product.stock_qty is not None:
                decremented = await self._products.decrement_stock_if_available(
                    product_id, org_id, qty
                )

                if not decremented:
                    raise StockError(
                        str(product_id), float(qty), float(product.stock_qty)
                    )

                wo = WriteOff(
                    org_id=org_id,
                    order_item_id=order_item.id,
                    product_id=product_id,
                    qty=qty,
                    reason="order_creation",
                )
                await self._writeoffs.add(wo)

    async def get_order(self, order_id: str | UUID) -> Order | None:
        return await self._orders.get_by_id(order_id)

    async def get_order_in_org(
        self, order_id: str | UUID, org_id: str | UUID
    ) -> Order | None:
        """Composite lookup (org_id, id) - 404 semantics at the router level."""

        return await self._orders.get_by_id_and_org(order_id, org_id)

    async def get_org_orders(self, org_id: str | UUID) -> list[Order]:
        return await self._orders.get_by_org(org_id)

    async def get_user_names(self, user_ids: Iterable) -> dict[str, str]:
        users = await UserRepository(self.uow.session).get_by_ids(user_ids)

        return {str(u.id): u.full_name for u in users}

    async def get_client_names(self, client_ids: Iterable) -> dict[str, str]:
        clients = await ClientRepository(self.uow.session).get_by_ids(client_ids)

        return {str(c.id): f"{c.name} {c.surname}" for c in clients}

    async def get_order_detail(
        self, order_id: str | UUID, org_id: str | UUID
    ) -> dict | None:
        order = await self._orders.get_by_id_and_org(order_id, org_id)

        if not order:
            return None

        items = await self._items.get_by_order(order.id)
        client_name = ""

        if order.client_id:
            client = await ClientRepository(self.uow.session).get_by_id(order.client_id)

            if client:
                client_name = f"{client.name} {client.surname}"

        creator_name = ""

        if order.created_by:
            creator = await UserRepository(self.uow.session).get_by_id(order.created_by)

            if creator:
                creator_name = creator.full_name

        updater_name = ""

        if order.updated_by:
            updater = await UserRepository(self.uow.session).get_by_id(order.updated_by)

            if updater:
                updater_name = updater.full_name

        return {
            "order": order,
            "items": items,
            "client_name": client_name,
            "creator_name": creator_name,
            "updater_name": updater_name,
        }

    async def _build_order_response(
        self, order: Order, items: list[OrderItem]
    ) -> OrderResponse:
        client_name = ""

        if order.client_id:
            client = await ClientRepository(self.uow.session).get_by_id(order.client_id)

            if client:
                client_name = f"{client.name} {client.surname}"

        return OrderResponse(
            id=order.id,
            org_id=order.org_id,
            client_id=order.client_id,
            client_name=client_name,
            status=order.status,
            total=float(order.total),
            execution_date=order.execution_date,
            notes=order.notes,
            photos=order.photos or [],
            local_fields=order.local_fields or {},
            custom_fields=order.custom_fields or {},
            is_deleted=order.is_deleted,
            items=[OrderItemResponse.model_validate(i) for i in items],
        )

    async def get_org_client_orders(
        self, org_id: str | UUID, client_id: str | UUID
    ) -> list[Order]:
        return await self._orders.get_by_org_and_client(org_id, client_id)

    async def get_client_orders(
        self, org_id: str | UUID, client_id: str | UUID
    ) -> list[OrderResponse]:
        client = await ClientRepository(self.uow.session).get_by_id(client_id)

        if not client:
            return []

        orders = await self._orders.get_by_org_and_client(org_id, client_id)
        items_map = await self._items.get_items_map_for_orders([o.id for o in orders])
        client_name = f"{client.name} {client.surname}"

        result = []

        for o in orders:
            items = items_map.get(o.id, [])
            result.append(
                OrderResponse(
                    id=o.id,
                    org_id=o.org_id,
                    client_id=o.client_id,
                    client_name=client_name,
                    status=o.status,
                    total=float(o.total),
                    execution_date=o.execution_date,
                    notes=o.notes,
                    photos=o.photos or [],
                    local_fields=o.local_fields or {},
                    custom_fields=o.custom_fields or {},
                    is_deleted=o.is_deleted,
                    items=[OrderItemResponse.model_validate(i) for i in items],
                )
            )

        return result

    async def get_filtered(
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
    ) -> tuple[list[Order], str | None, int, dict, dict]:
        try:
            return await self._orders.get_filtered(
                org_id=org_id,
                cursor=cursor,
                limit=limit,
                status=status,
                execution_date_from=execution_date_from,
                execution_date_to=execution_date_to,
                created_from=created_from,
                created_to=created_to,
                sort=sort,
                include_deleted=include_deleted,
            )
        except ValueError as e:
            raise ValidationException(str(e)) from e

    async def get_by_date_range(
        self, org_id: str | UUID, date_from: str, date_to: str
    ) -> list[Order]:
        return await self._orders.get_by_date_range(org_id, date_from, date_to)

    async def add_item(
        self,
        order_id: str | UUID,
        product_id: str | None,
        name: str,
        price: Decimal = Decimal("0"),
        qty: Decimal = Decimal(1),
        org_id: str | UUID | None = None,
    ) -> OrderItem:
        async with self.uow:
            if org_id is not None:
                order = await self._orders.get_by_id_and_org(order_id, org_id)

                if not order:
                    raise NotFoundException(f"Order not found: {order_id}")

                if product_id:
                    product = await self._products.get_by_id_and_org(product_id, org_id)

                    if not product:
                        raise NotFoundException(f"Product not found: {product_id}")

            item = OrderItem(
                order_id=_as_uuid(order_id),
                product_id=product_id or None,
                name=name,
                price=price,
                qty=qty,
            )
            item = await self._items.add(item)
            await self._recalc_total(order_id)

            logger.info(
                "order_item_added",
                order_id=str(order_id),
                org_id=str(org_id) if org_id else None,
                item_id=str(item.id),
                product_id=product_id or None,
            )

            return item

    async def update_item(
        self,
        order_id: str | UUID,
        item_id: str | UUID,
        org_id: str | UUID,
        name: str | None = None,
        price: Decimal | None = None,
        qty: Decimal | None = None,
    ) -> OrderItem:
        async with self.uow:
            order = await self._orders.get_by_id_and_org(order_id, org_id)

            if not order:
                raise NotFoundException(f"Order not found: {order_id}")

            item = await self._items.get_by_id(item_id)

            if not item or str(item.order_id) != str(order.id):
                raise NotFoundException(f"Item not found: {item_id}")

            if name is not None:
                item.name = name

            if price is not None:
                if price < 0:
                    raise ValidationException("Item price must be >= 0")

                item.price = price

            if qty is not None:
                if qty <= 0:
                    raise ValidationException("Item qty must be > 0")

                if qty != item.qty:
                    existing = await self._writeoffs.get_by_order_item(item.id)

                    if existing:
                        raise ConflictException(
                            "Cannot change qty of an order item "
                            "with an existing write-off"
                        )

                item.qty = qty

            await self.uow.session.flush()
            await self.uow.session.refresh(item)
            await self._recalc_total(order_id)

            logger.info(
                "order_item_updated",
                order_id=str(order_id),
                org_id=str(org_id),
                item_id=str(item.id),
            )

            return item

    async def remove_item(
        self,
        order_id: str | UUID,
        item_id: str | UUID,
        org_id: str | UUID,
    ) -> None:
        async with self.uow:
            order = await self._orders.get_by_id_and_org(order_id, org_id)

            if not order:
                raise NotFoundException(f"Order not found: {order_id}")

            item = await self._items.get_by_id(item_id)

            if not item or str(item.order_id) != str(order.id):
                raise NotFoundException(f"Item not found: {item_id}")

            existing = await self._writeoffs.get_by_order_item(item.id)

            if existing:
                raise ConflictException(
                    "Cannot remove order item with an existing write-off"
                )

            await self._items.delete(item)

            logger.info(
                "order_item_removed",
                order_id=str(order_id),
                org_id=str(org_id),
                item_id=str(item_id),
            )

            await self._recalc_total(order_id)

    async def get_items(
        self, order_id: str | UUID, org_id: str | UUID | None = None
    ) -> list[OrderItem]:
        if org_id is not None:
            order = await self._orders.get_by_id_and_org(order_id, org_id)

            if not order:
                raise NotFoundException(f"Order not found: {order_id}")

        return await self._items.get_by_order(order_id)

    async def write_off_for_order_item(
        self,
        org_id: str | UUID,
        order_id: str | UUID,
        order_item_id: str | UUID,
        qty: Decimal,
        reason: str | None = None,
    ) -> WriteOff:
        if qty <= 0:
            raise ValidationException("Write-off qty must be greater than 0")

        async with self.uow:
            order = await self._orders.get_by_id_and_org(order_id, org_id)

            if not order:
                raise NotFoundException(f"Order not found: {order_id}")

            item = await self._items.get_by_id(order_item_id)

            if not item or str(item.order_id) != str(order.id):
                raise NotFoundException(f"Order item not found: {order_item_id}")

            product_id = item.product_id

            if not product_id:
                raise ValidationException("Order item has no product to write off")

            existing_writeoffs = await self._writeoffs.get_by_order_item(item.id)

            if existing_writeoffs:
                raise ConflictException(
                    "Write-off already exists for this order item",
                    code="WRITEOFF_EXISTS",
                )

            product = await self._products.get_by_id_and_org(product_id, org_id)

            if not product:
                raise NotFoundException(f"Product not found: {product_id}")

            # Service products / inventory not tracked -> stock is never touched.
            if product.track_inventory and product.stock_qty is not None:
                decremented = await self._products.decrement_stock_if_available(
                    product_id, org_id, qty
                )

                if not decremented:
                    raise StockError(
                        str(product_id), float(qty), float(product.stock_qty)
                    )

            wo = WriteOff(
                org_id=org_id,
                order_item_id=item.id,
                product_id=product_id,
                qty=qty,
                reason=reason if reason is not None else "production",
            )

            try:
                wo = await self._writeoffs.add(wo)
            except IntegrityError as e:
                # DB-level backstop for the concurrent double write-off race
                # (uq_write_offs_order_item).
                raise ConflictException(
                    "Write-off already exists for this order item",
                    code="WRITEOFF_EXISTS",
                ) from e
            logger.info(
                "stock_write_off",
                org_id=org_id,
                order_id=str(order_id),
                order_item_id=str(order_item_id),
                product_id=product_id or None,
                qty=float(qty),
                reason=wo.reason,
            )
            return wo

    async def write_off_bulk(
        self,
        order_id: str | UUID,
        org_id: str | UUID,
        qty_by_item_id: dict[str, Decimal],
    ) -> None:
        if not qty_by_item_id:
            return

        async with self.uow:
            for item_id, qty in qty_by_item_id.items():
                if qty > 0:
                    await self.write_off_for_order_item(
                        org_id=org_id,
                        order_id=order_id,
                        order_item_id=item_id,
                        qty=qty,
                    )

    async def change_status(
        self,
        order_id: str | UUID,
        status: str,
        updated_by: str | UUID | None = None,
    ) -> Order | None:
        async with self.uow:
            order = await self._orders.get_by_id(order_id)

            if not order:
                return None

            order.status = status
            order.updated_by = _as_uuid(updated_by)
            await self.uow.session.flush()
            await self.uow.session.refresh(order)

            logger.info(
                "order_status_changed",
                order_id=str(order.id),
                status=status,
                updated_by=str(updated_by) if updated_by else None,
            )

            return order

    async def delete_order(
        self, order_id: str | UUID, updated_by: str | UUID | None = None
    ) -> bool:
        async with self.uow:
            order = await self._orders.get_by_id(order_id)

            if not order:
                return False

            order.is_deleted = True
            order.updated_by = _as_uuid(updated_by)
            await self.uow.session.flush()

            logger.info(
                "order_deleted",
                order_id=str(order_id),
                updated_by=str(updated_by) if updated_by else None,
            )

            return True

    async def change_status_in_org(
        self,
        order_id: str | UUID,
        org_id: str | UUID,
        status: str,
        updated_by: str | UUID | None = None,
    ) -> OrderResponse | None:
        async with self.uow:
            order = await self._orders.get_by_id_and_org(order_id, org_id)

            if not order:
                return None

            order.status = status
            order.updated_by = _as_uuid(updated_by)
            await self.uow.session.flush()
            await self.uow.session.refresh(order)

            logger.info(
                "order_status_changed",
                order_id=str(order.id),
                org_id=org_id,
                status=status,
                updated_by=str(updated_by) if updated_by else None,
            )

            items = await self._items.get_by_order(order.id)

            return await self._build_order_response(order, items)

    async def delete_order_in_org(
        self,
        order_id: str | UUID,
        org_id: str | UUID,
        updated_by: str | UUID | None = None,
    ) -> bool:
        async with self.uow:
            order = await self._orders.get_by_id_and_org(order_id, org_id)

            if not order:
                return False

            order.is_deleted = True
            order.updated_by = _as_uuid(updated_by)
            await self.uow.session.flush()

            logger.info(
                "order_deleted",
                order_id=str(order_id),
                org_id=org_id,
                updated_by=str(updated_by) if updated_by else None,
            )

            return True

    async def _recalc_total(self, order_id: str | UUID) -> None:
        items = await self._items.get_by_order(order_id)
        total = sum((item.price * item.qty for item in items), start=Decimal("0"))
        order = await self._orders.get_by_id(order_id)

        if order:
            order.total = total
            await self.uow.session.flush()
