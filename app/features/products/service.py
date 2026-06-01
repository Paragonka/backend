from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.core.log import get_logger
from app.core.uow import AppUnitOfWork
from app.features.eav.service import EavAttributeService
from app.features.products.models import Product, ProductComponent
from app.features.products.repository import ProductRepository
from app.features.products.schemas import ProductComponentInput
from app.shared.constants import ENTITY_TYPE_PRODUCT, PRODUCT_TYPE_GOOD
from app.shared.exceptions import ConflictException, ValidationException
from app.shared.sanitization import strip_html_tags

logger = get_logger(__name__)

ComponentLike = ProductComponentInput | dict[str, object]


class ProductService:
    def __init__(self, uow: AppUnitOfWork):
        self.uow = uow

    @property
    def _products(self) -> ProductRepository:
        return ProductRepository(self.uow.session)

    async def create_product(
        self,
        org_id: str,
        name: str,
        category: str = "",
        unit: str = "шт",
        product_type: str = PRODUCT_TYPE_GOOD,
        price: Decimal = Decimal("0"),
        cost_price: Decimal = Decimal("0"),
        stock_qty: Decimal | None = None,
        track_inventory: bool = False,
        is_sellable: bool = True,
        is_active: bool = True,
        custom_fields: dict | None = None,
        local_fields: dict | None = None,
        components: Sequence[ComponentLike] | None = None,
    ) -> Product:
        async with self.uow:
            if custom_fields:
                attrs = await self.uow.eav_attributes.get_by_entity_code(
                    org_id, ENTITY_TYPE_PRODUCT
                )
                EavAttributeService.validate_custom_fields(custom_fields, attrs)

            product = Product(
                org_id=org_id,
                name=strip_html_tags(name),
                category=strip_html_tags(category),
                unit=unit,
                product_type=product_type,
                price=price,
                cost_price=cost_price,
                stock_qty=stock_qty,
                track_inventory=track_inventory,
                is_sellable=is_sellable,
                is_active=is_active,
                custom_fields=custom_fields or {},
                local_fields=local_fields or {},
            )

            try:
                product = await self._products.add(product)
            except IntegrityError as e:
                raise ConflictException(
                    f"Product with name '{name}' and unit '{unit}' already exists",
                    code="PRODUCT_EXISTS",
                ) from e

            await self._replace_components(product, org_id, components or [])
            await self.uow.session.flush()

            logger.info("product_created", product_id=str(product.id), org_id=org_id)
            return product

    async def upsert_product(
        self,
        org_id: str,
        name: str,
        category: str = "",
        unit: str = "шт",
        product_type: str = PRODUCT_TYPE_GOOD,
        price: Decimal = Decimal("0"),
        cost_price: Decimal = Decimal("0"),
        stock_qty: Decimal | None = None,
        track_inventory: bool = False,
        is_sellable: bool = True,
        is_active: bool = True,
        custom_fields: dict | None = None,
        local_fields: dict | None = None,
        components: Sequence[ComponentLike] | None = None,
    ) -> tuple[Product, str]:
        """Deduplicate by key (name, unit). Returns created|updated."""

        async with self.uow:
            existing = await self._products.get_by_name_unit(org_id, name, unit)

            if existing:
                await self._apply_updates(
                    existing,
                    org_id,
                    category,
                    product_type,
                    price,
                    cost_price,
                    stock_qty,
                    track_inventory,
                    is_sellable,
                    is_active,
                    custom_fields,
                    local_fields,
                    components,
                )
                session = self.uow.session

                if session is not None:
                    await session.flush()
                    await session.refresh(existing)

                logger.info(
                    "product_updated",
                    product_id=str(existing.id),
                    org_id=str(existing.org_id),
                )

                return existing, "updated"

            if custom_fields:
                attrs = await self.uow.eav_attributes.get_by_entity_code(
                    org_id, ENTITY_TYPE_PRODUCT
                )
                EavAttributeService.validate_custom_fields(custom_fields, attrs)

            product = Product(
                org_id=org_id,
                name=strip_html_tags(name),
                category=strip_html_tags(category),
                unit=unit,
                product_type=product_type,
                price=price,
                cost_price=cost_price,
                stock_qty=stock_qty,
                track_inventory=track_inventory,
                is_sellable=is_sellable,
                is_active=is_active,
                custom_fields=custom_fields or {},
                local_fields=local_fields or {},
            )

            try:
                product = await self._products.add(product)
            except IntegrityError:
                # Concurrent upsert with the same (name, unit) won the race
                # (uq_products_org_name_unit). Fall back to the update path.
                await self.uow.session.rollback()
                existing = await self._products.get_by_name_unit(org_id, name, unit)

                if not existing:
                    raise

                await self._apply_updates(
                    existing,
                    org_id,
                    category,
                    product_type,
                    price,
                    cost_price,
                    stock_qty,
                    track_inventory,
                    is_sellable,
                    is_active,
                    custom_fields,
                    local_fields,
                    components,
                )
                await self.uow.session.flush()
                await self.uow.session.refresh(existing)

                return existing, "updated"

            await self._replace_components(product, org_id, components or [])
            await self.uow.session.flush()

            logger.info("product_created", product_id=str(product.id), org_id=org_id)
            return product, "created"

    async def _apply_updates(
        self,
        existing: Product,
        org_id: str,
        category: str,
        product_type: str,
        price: Decimal,
        cost_price: Decimal,
        stock_qty: Decimal | None,
        track_inventory: bool,
        is_sellable: bool,
        is_active: bool,
        custom_fields: dict | None,
        local_fields: dict | None,
        components: Sequence[ComponentLike] | None,
    ) -> None:
        merged = {**existing.custom_fields, **(custom_fields or {})}

        if merged:
            attrs = await self.uow.eav_attributes.get_by_entity_code(
                org_id, ENTITY_TYPE_PRODUCT
            )
            EavAttributeService.validate_custom_fields(merged, attrs)

        if category:
            existing.category = strip_html_tags(category)

        if product_type:
            existing.product_type = product_type

        existing.price = Decimal(str(price))
        existing.cost_price = Decimal(str(cost_price))

        if stock_qty is not None:
            existing.stock_qty = Decimal(str(stock_qty))

        existing.track_inventory = track_inventory
        existing.is_sellable = is_sellable
        existing.is_active = is_active

        if custom_fields is not None:
            existing.custom_fields = merged

        if local_fields is not None:
            existing.local_fields = {
                **existing.local_fields,
                **local_fields,
            }

        if components is not None:
            await self._replace_components(existing, org_id, components)

    async def _replace_components(
        self,
        product: Product,
        org_id: str,
        components: Sequence[ComponentLike],
    ) -> None:
        normalized: list[tuple[UUID, Decimal]] = []
        seen: set[UUID] = set()

        for component in components:
            if isinstance(component, dict):
                component_id = component["product_id"]
                quantity = component["quantity"]
            else:
                component_id = component.product_id
                quantity = component.quantity

            component_id = UUID(str(component_id))

            if component_id == product.id:
                raise ValidationException(
                    "Продукт не может входить сам в себя",
                    code="PRODUCT_COMPONENT_INVALID",
                )

            if component_id in seen:
                raise ValidationException(
                    "Один и тот же продукт нельзя добавить в состав дважды",
                    code="PRODUCT_COMPONENT_INVALID",
                )

            seen.add(component_id)
            normalized.append((component_id, Decimal(str(quantity))))

        available = await self._products.get_by_ids_and_org(
            [component_id for component_id, _quantity in normalized], org_id
        )

        if len(available) != len(normalized):
            raise ValidationException(
                "Все продукты состава должны принадлежать текущей организации",
                code="PRODUCT_COMPONENT_INVALID",
            )

        product.components = [
            ProductComponent(
                product_id=product.id,
                component_id=component_id,
                quantity=quantity,
            )
            for component_id, quantity in normalized
        ]

    async def _apply_update_fields(self, product: Product, fields: dict) -> None:
        """Mutation core shared by update_product and update_product_in_org."""

        custom_fields = fields.get("custom_fields")
        local_fields = fields.get("local_fields")
        components = fields.get("components")

        if custom_fields is not None:
            attrs = await self.uow.eav_attributes.get_by_entity_code(
                product.org_id, ENTITY_TYPE_PRODUCT
            )
            EavAttributeService.validate_custom_fields(custom_fields, attrs)
            product.custom_fields = custom_fields

        if local_fields is not None:
            product.local_fields = local_fields

        if components is not None:
            await self._replace_components(product, str(product.org_id), components)

        self._apply_scalar_fields(product, fields)

    def _apply_scalar_fields(self, product: Product, fields: dict) -> None:
        name = fields.get("name")

        if name is not None:
            product.name = strip_html_tags(name)

        category = fields.get("category")

        if category is not None:
            product.category = strip_html_tags(category)

        for key in (
            "unit",
            "product_type",
            "price",
            "cost_price",
            "stock_qty",
            "track_inventory",
            "is_sellable",
            "is_active",
        ):
            value = fields.get(key)

            if value is not None:
                setattr(product, key, value)

    async def update_product_in_org(
        self,
        product_id: str | UUID,
        org_id: str | UUID,
        **fields,
    ) -> Product | None:
        """Composite lookup + mutation in one transaction - 404 semantics at
        the router level (no check-then-mutate)."""

        async with self.uow:
            product = await self._products.get_by_id_and_org(product_id, org_id)

            if not product:
                return None

            await self._apply_update_fields(product, fields)
            await self.uow.session.flush()
            await self.uow.session.refresh(product)

            logger.info(
                "product_updated",
                product_id=str(product.id),
                org_id=str(product.org_id),
            )
            return product

    async def get_product_in_org(
        self, product_id: str | UUID, org_id: str | UUID
    ) -> Product | None:
        """Composite lookup (org_id, id) - 404 semantics at the router level."""

        return await self._products.get_by_id_and_org(product_id, org_id)

    async def get_org_products(self, org_id: str | UUID) -> list[Product]:
        return await self._products.get_by_org(org_id)

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
        try:
            return await self._products.get_filtered(
                org_id=org_id,
                cursor=cursor,
                limit=limit,
                name=name,
                category=category,
                product_type=product_type,
                is_active=is_active,
                eav_filters=eav_filters,
                sort=sort,
            )
        except ValueError as e:
            raise ValidationException(str(e)) from e

    async def _delete_product_record(self, product: Product) -> None:
        # Order items, write-offs and receipt items store snapshot data
        # (name/price/qty), so deleting a product never affects them -
        # the FK is ON DELETE SET NULL.
        if await self._products.exists_as_component(product.id):
            logger.warning(
                "product_delete_blocked",
                product_id=str(product.id),
                org_id=str(product.org_id),
                reason="used_as_component",
            )
            raise ConflictException(
                "Cannot delete product: it is a component of another product",
                code="PRODUCT_IN_USE",
            )

        await self._products.delete(product)
        logger.info(
            "product_deleted", product_id=str(product.id), org_id=str(product.org_id)
        )

    async def delete_product_in_org(
        self, product_id: str | UUID, org_id: str | UUID
    ) -> bool:
        """Composite lookup + delete in one transaction - 404 semantics at the
        router level (no check-then-mutate)."""

        async with self.uow:
            product = await self._products.get_by_id_and_org(product_id, org_id)

            if not product:
                return False

            await self._delete_product_record(product)

            return True
