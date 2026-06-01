from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.products.models import Product, ProductComponent
from app.shared.exceptions import NotFoundException
from app.shared.filtering import (
    apply_sort,
    build_cursor_response,
    count_query,
    paginate_query,
)
from app.shared.sanitization import escape_like


class ProductRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, product: Product) -> Product:
        self.session.add(product)
        await self.session.flush()
        await self.session.refresh(product)

        return product

    async def get_by_id_and_org(
        self, product_id: str | UUID, org_id: str | UUID
    ) -> Product | None:
        if isinstance(product_id, str):
            try:
                product_id = UUID(product_id)
            except ValueError:
                raise NotFoundException(f"Product not found: {product_id}") from None

        if isinstance(org_id, str):
            try:
                org_id = UUID(org_id)
            except ValueError:
                raise NotFoundException(f"Organization not found: {org_id}") from None

        result = await self.session.execute(
            select(Product).where(Product.id == product_id, Product.org_id == org_id)
        )

        return result.scalar_one_or_none()

    async def get_by_org(self, org_id: str | UUID) -> list[Product]:
        if isinstance(org_id, str):
            org_id = UUID(org_id)

        result = await self.session.execute(
            select(Product).where(Product.org_id == org_id).order_by(Product.name)
        )

        return list(result.scalars().all())

    async def get_by_ids_and_org(
        self, product_ids: list[UUID], org_id: str | UUID
    ) -> list[Product]:
        if not product_ids:
            return []

        if isinstance(org_id, str):
            org_id = UUID(org_id)

        result = await self.session.execute(
            select(Product).where(
                Product.org_id == org_id,
                Product.id.in_(product_ids),
            )
        )

        return list(result.scalars().all())

    async def exists_as_component(self, product_id: str | UUID) -> bool:
        product_id = self._to_uuid(product_id)
        result = await self.session.execute(
            select(ProductComponent.product_id)
            .where(ProductComponent.component_id == product_id)
            .limit(1)
        )

        return result.scalar_one_or_none() is not None

    async def get_by_name_unit(
        self, org_id: str | UUID, name: str, unit: str
    ) -> Product | None:
        if isinstance(org_id, str):
            org_id = UUID(org_id)

        result = await self.session.execute(
            select(Product).where(
                Product.org_id == org_id,
                Product.name == name,
                Product.unit == unit,
            )
        )

        return result.scalar_one_or_none()

    async def get_filtered(
        self,
        org_id: str | UUID,
        cursor: str | None = None,
        limit: int = 50,
        name: str | None = None,
        category: str | None = None,
        product_type: str | None = None,
        is_active: bool | None = None,
        eav_filters: dict[str, str] | None = None,
        sort: str | None = None,
    ) -> tuple[list[Product], str | None, int]:
        if isinstance(org_id, str):
            org_id = UUID(org_id)

        query = select(Product).where(Product.org_id == org_id)

        if name:
            query = query.where(
                Product.name.ilike(f"%{escape_like(name)}%", escape="\\")
            )

        if category:
            query = query.where(
                Product.category.ilike(f"%{escape_like(category)}%", escape="\\")
            )

        if product_type:
            query = query.where(Product.product_type == product_type)

        if is_active is not None:
            query = query.where(Product.is_active == is_active)

        if eav_filters:
            for code, value in eav_filters.items():
                query = query.where(Product.custom_fields[code].as_string() == value)

        total = await count_query(self.session, query)
        sort_map = {
            "name": Product.name,
            "price": Product.price,
            "category": Product.category,
            "created_at": Product.id,
        }
        query, sort_col, sort_desc = apply_sort(query, sort, sort_map, default="name")
        keyset = sort_col is not None and sort_col is not Product.id
        query, effective_limit = paginate_query(
            query,
            cursor,
            limit,
            id_column=Product.id,
            sort_column=sort_col if keyset else None,
            sort_desc=sort_desc,
        )
        result = await self.session.execute(query)
        items = list(result.scalars().all())
        items, next_cursor = build_cursor_response(
            items,
            effective_limit,
            sort_attr=sort_col.name
            if (sort_col is not None and sort_col is not Product.id)
            else None,
        )

        return items, next_cursor, total

    async def delete(self, product: Product) -> None:
        await self.session.delete(product)
        await self.session.flush()

    async def decrement_stock_if_available(
        self, product_id: str | UUID, org_id: str | UUID, qty: Decimal
    ) -> bool:
        """Atomically decrement stock if enough is available.

        No read-modify-write race: single conditional UPDATE - the row lock
        plus WHERE stock_qty >= :qty guarantees no lost updates under
        concurrency. Returns True if decremented.
        """
        stmt = (
            update(Product)
            .where(
                Product.id == self._to_uuid(product_id),
                Product.org_id == self._to_uuid(org_id, "Organization not found"),
                Product.track_inventory.is_(True),
                Product.stock_qty.is_not(None),
                Product.stock_qty >= qty,
            )
            .values(stock_qty=Product.stock_qty - qty)
            .execution_options(synchronize_session=False)
        )
        result = cast(CursorResult, await self.session.execute(stmt))

        return result.rowcount > 0

    @staticmethod
    def _to_uuid(value: str | UUID, message: str = "Product not found") -> UUID:
        if isinstance(value, UUID):
            return value

        try:
            return UUID(value)
        except ValueError:
            raise NotFoundException(f"{message}: {value}") from None
