from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.receipts.models import Receipt, ReceiptItem
from app.shared.exceptions import NotFoundException
from app.shared.filtering import build_cursor_response, paginate_query


class ReceiptRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, receipt: Receipt) -> Receipt:
        self.session.add(receipt)
        await self.session.flush()
        await self.session.refresh(receipt)

        return receipt

    async def get_by_id_and_org(
        self, receipt_id: str | UUID, org_id: str | UUID
    ) -> Receipt | None:
        if isinstance(receipt_id, str):
            try:
                receipt_id = UUID(receipt_id)
            except ValueError:
                raise NotFoundException(f"Receipt not found: {receipt_id}") from None

        if isinstance(org_id, str):
            org_id = UUID(org_id)

        result = await self.session.execute(
            select(Receipt).where(Receipt.id == receipt_id, Receipt.org_id == org_id)
        )

        return result.scalar_one_or_none()

    async def get_by_org(self, org_id: str | UUID) -> list[Receipt]:
        if isinstance(org_id, str):
            org_id = UUID(org_id)

        # uuid7 is monotonic by time - one id DESC ordering
        # (matches get_filtered; previously this used receipt_date DESC).
        result = await self.session.execute(
            select(Receipt).where(Receipt.org_id == org_id).order_by(Receipt.id.desc())
        )

        return list(result.scalars().all())

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
        if isinstance(org_id, str):
            org_id = UUID(org_id)

        query = select(Receipt).where(Receipt.org_id == org_id)

        if date_from:
            query = query.where(Receipt.receipt_date >= date_from)

        if date_to:
            query = query.where(Receipt.receipt_date <= date_to)

        if source:
            query = query.where(Receipt.source == source)

        if client_id:
            query = query.where(Receipt.client_id == UUID(client_id))

        query, effective_limit = paginate_query(
            query,
            cursor,
            limit,
            id_column=Receipt.id,
            sort_desc=True,  # one id DESC ordering (uuid7)
        )
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return build_cursor_response(items, effective_limit)

    async def delete(self, receipt: Receipt) -> None:
        await self.session.delete(receipt)
        await self.session.flush()


class ReceiptItemRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, item: ReceiptItem) -> ReceiptItem:
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)

        return item

    async def get_by_receipt(self, receipt_id: str | UUID) -> list[ReceiptItem]:
        if isinstance(receipt_id, str):
            try:
                receipt_id = UUID(receipt_id)
            except ValueError:
                raise NotFoundException(f"Receipt not found: {receipt_id}") from None

        result = await self.session.execute(
            select(ReceiptItem).where(ReceiptItem.receipt_id == receipt_id)
        )

        return list(result.scalars().all())

    async def delete(self, item: ReceiptItem) -> None:
        await self.session.delete(item)
        await self.session.flush()
