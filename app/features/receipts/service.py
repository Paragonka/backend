from uuid import UUID

from app.core.log import get_logger
from app.core.uow import AppUnitOfWork
from app.features.clients.repository import ClientRepository
from app.features.orders.repository import OrderRepository
from app.features.receipts.jpk_parser import parse_jpk
from app.features.receipts.models import Receipt, ReceiptItem
from app.features.receipts.repository import ReceiptItemRepository, ReceiptRepository
from app.features.receipts.schemas import ReceiptItemCreate
from app.shared.exceptions import NotFoundException, ValidationException

logger = get_logger(__name__)


class ReceiptParseError(Exception):
    def __init__(
        self,
        message: str,
        details: list | None = None,
        format_detected: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.details = details or []
        self.format_detected = format_detected


class ReceiptService:
    def __init__(self, uow: AppUnitOfWork):
        self.uow = uow

    @property
    def _receipts(self) -> ReceiptRepository:
        return ReceiptRepository(self.uow.session)

    @property
    def _items(self) -> ReceiptItemRepository:
        return ReceiptItemRepository(self.uow.session)

    # C901: item and relationship validation + creation in one transaction;
    # splitting it would complicate the flow without benefit
    async def create_receipt(  # noqa: C901
        self,
        org_id: str,
        items_data: list[ReceiptItemCreate],
        client_id: str | None = None,
        order_id: str | None = None,
        receipt_date: str = "",
        source: str | None = None,
        raw_data: dict | None = None,
        notes: str | None = None,
    ) -> Receipt:
        if not items_data:
            raise ValidationException("Receipt must have at least one item")

        for item in items_data:
            if item.price <= 0:
                raise ValidationException(
                    f"Item '{item.name}' price must be greater than 0"
                )

            if item.qty <= 0:
                raise ValidationException(
                    f"Item '{item.name}' qty must be greater than 0"
                )

        total = sum(item.price * item.qty for item in items_data)

        async with self.uow:
            if client_id is not None:
                try:
                    client = await ClientRepository(self.uow.session).get_by_id_and_org(
                        client_id, org_id
                    )
                except NotFoundException as e:
                    raise ValidationException("Client not found") from e

                if not client:
                    raise ValidationException("Client not found")

            if order_id is not None:
                try:
                    order = await OrderRepository(self.uow.session).get_by_id_and_org(
                        order_id, org_id
                    )
                except NotFoundException as e:
                    raise ValidationException("Order not found") from e

                if not order:
                    raise ValidationException("Order not found")

            receipt = Receipt(
                org_id=org_id,
                client_id=client_id,
                order_id=order_id,
                receipt_date=receipt_date,
                total=total,
                source=source,
                raw_data=raw_data,
                notes=notes,
            )
            receipt = await self._receipts.add(receipt)

            for item_data in items_data:
                item = ReceiptItem(
                    receipt_id=receipt.id,
                    product_id=item_data.product_id,
                    name=item_data.name,
                    price=item_data.price,
                    qty=item_data.qty,
                )
                await self._items.add(item)

            logger.info(
                "receipt_created",
                receipt_id=str(receipt.id),
                org_id=org_id,
                source=source or "manual",
                item_count=len(items_data),
                total=float(total),
                client_id=str(client_id) if client_id else None,
                order_id=str(order_id) if order_id else None,
            )

            return receipt

    async def create_receipt_from_jpk(
        self, org_id: str, json_data: dict, source: str = "jpk"
    ) -> Receipt:
        """Parse a JPK document and create a receipt from it (orchestration)."""

        result = parse_jpk(json_data)

        if result.has_errors or not result.items:
            logger.warning(
                "receipt_parse_failed",
                org_id=org_id,
                format_detected=result.format_detected,
                error_count=len(result.errors),
                errors=result.errors[:10],
            )
            raise ReceiptParseError(
                "Не удалось распарсить чек",
                details=result.errors,
                format_detected=result.format_detected,
            )

        notes = (
            f"JPK [{result.format_detected}] {result.seller_name} "
            f"TIN:{result.tin}".strip()
        )

        return await self.create_receipt(
            org_id=org_id,
            items_data=result.items,
            receipt_date=result.receipt_date,
            source=result.source or source,
            raw_data=result.raw_data or json_data,
            notes=notes,
        )

    async def get_receipt_in_org(
        self, receipt_id: str | UUID, org_id: str | UUID
    ) -> Receipt | None:
        return await self._receipts.get_by_id_and_org(receipt_id, org_id)

    async def get_org_receipts(self, org_id: str | UUID) -> list[Receipt]:
        return await self._receipts.get_by_org(org_id)

    async def get_filtered(
        self,
        org_id: str | UUID,
        cursor: str | None = None,
        limit: int = 50,
        date_from: str | None = None,
        date_to: str | None = None,
        source: str | None = None,
        client_id: str | None = None,
    ) -> tuple[list[Receipt], str | None]:
        try:
            return await self._receipts.get_filtered(
                org_id=org_id,
                cursor=cursor,
                limit=limit,
                date_from=date_from,
                date_to=date_to,
                source=source,
                client_id=client_id,
            )
        except ValueError as e:
            raise ValidationException(str(e)) from e

    async def get_items(self, receipt_id: str | UUID) -> list[ReceiptItem]:
        return await self._items.get_by_receipt(receipt_id)

    async def delete_receipt_in_org(
        self, receipt_id: str | UUID, org_id: str | UUID
    ) -> bool:
        async with self.uow:
            receipt = await self._receipts.get_by_id_and_org(receipt_id, org_id)

            if not receipt:
                return False

            items = await self._items.get_by_receipt(receipt.id)

            for item in items:
                await self._items.delete(item)

            await self._receipts.delete(receipt)

            logger.info(
                "receipt_deleted",
                receipt_id=str(receipt.id),
                org_id=str(receipt.org_id),
            )

            return True
