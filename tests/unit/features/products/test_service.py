from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.features.eav.models import EavAttribute
from app.features.products.repository import ProductRepository
from app.features.products.service import ProductService
from app.shared.exceptions import NotFoundException

ORG_ID = "06a2502b-6534-7779-8000-4ff242017bf0"


class TestProductService:
    async def test_create_product(self, mock_session, mock_uow):
        async def refresh_side_effect(obj):
            obj.id = uuid4()

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)

        service = ProductService(mock_uow)
        product = await service.create_product(
            ORG_ID,
            "Croissant",
            price=Decimal("150.0"),
            cost_price=Decimal("80.0"),
            unit="шт",
        )

        mock_session.add.assert_called()
        assert product.name == "Croissant"
        assert product.unit == "шт"
        assert product.product_type == "good"

    async def test_create_product_material(self, mock_session, mock_uow):
        async def refresh_side_effect(obj):
            obj.id = uuid4()

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)

        service = ProductService(mock_uow)
        product = await service.create_product(
            ORG_ID,
            "Масло",
            product_type="material",
            track_inventory=True,
            stock_qty=Decimal("5.0"),
        )

        assert product.product_type == "material"
        assert product.track_inventory is True
        assert product.stock_qty == 5.0

    async def test_get_org_products(self, mock_session, mock_uow):
        p1 = MagicMock()
        p1.name = "Baguette"
        execute_result = MagicMock()
        execute_result.scalars.return_value.all.return_value = [p1]
        mock_session.execute.return_value = execute_result

        service = ProductService(mock_uow)
        products = await service.get_org_products(ORG_ID)

        assert len(products) == 1

    async def test_update_product_in_org(self, mock_session, mock_uow):
        product = MagicMock()
        product.name = "Old Name"
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = product
        mock_session.execute.return_value = execute_result

        service = ProductService(mock_uow)
        result = await service.update_product_in_org(uuid4(), ORG_ID, name="New Name")

        assert result is not None
        assert product.name == "New Name"
        mock_session.flush.assert_awaited()
        mock_session.refresh.assert_awaited()

    async def test_update_product_in_org_foreign_org_returns_none(
        self, mock_session, mock_uow
    ):
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = execute_result

        service = ProductService(mock_uow)
        result = await service.update_product_in_org(uuid4(), ORG_ID, name="New Name")

        assert result is None
        mock_session.flush.assert_not_awaited()
        mock_session.delete.assert_not_called()

    async def test_delete_product_in_org(self, mock_session, mock_uow, monkeypatch):
        product = MagicMock()
        product.id = uuid4()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = product
        mock_session.execute.return_value = execute_result
        monkeypatch.setattr(
            ProductRepository, "exists_as_component", AsyncMock(return_value=False)
        )

        service = ProductService(mock_uow)
        result = await service.delete_product_in_org(product.id, ORG_ID)

        assert result is True
        mock_session.delete.assert_called()

    async def test_delete_product_in_org_foreign_org_returns_false(
        self, mock_session, mock_uow
    ):
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = execute_result

        service = ProductService(mock_uow)
        result = await service.delete_product_in_org(uuid4(), ORG_ID)

        assert result is False
        mock_session.delete.assert_not_called()

    async def test_delete_product_in_org_used_as_component_raises_conflict(
        self, mock_session, mock_uow, monkeypatch
    ):
        from app.shared.exceptions import ConflictException

        product = MagicMock()
        product.id = uuid4()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = product
        mock_session.execute.return_value = execute_result
        monkeypatch.setattr(
            ProductRepository, "exists_as_component", AsyncMock(return_value=True)
        )

        service = ProductService(mock_uow)
        with pytest.raises(ConflictException) as exc_info:
            await service.delete_product_in_org(product.id, ORG_ID)

        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "PRODUCT_IN_USE"
        mock_session.delete.assert_not_called()


class TestProductServiceUpsert:
    async def test_upsert_creates_when_no_name_unit_match(self, mock_session, mock_uow):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        async def refresh_side_effect(obj):
            obj.id = uuid4()

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)

        service = ProductService(mock_uow)
        product, status_out = await service.upsert_product(
            ORG_ID, "Мука", unit="кг", price=Decimal("50")
        )

        mock_session.add.assert_called()
        assert status_out == "created"
        assert product.name == "Мука"
        assert product.unit == "кг"

    async def test_upsert_updates_existing_by_name_unit(self, mock_session, mock_uow):
        existing = MagicMock()
        existing.custom_fields = {}
        existing.local_fields = {}
        mock_session.execute.return_value.scalar_one_or_none.return_value = existing

        service = ProductService(mock_uow)
        product, status_out = await service.upsert_product(
            ORG_ID, "Мука", unit="кг", price=Decimal("60")
        )

        assert status_out == "updated"
        assert existing.price == 60
        assert product is existing

    async def test_upsert_different_unit_creates(self, mock_session, mock_uow):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        async def refresh_side_effect(obj):
            obj.id = uuid4()

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)

        service = ProductService(mock_uow)
        _, status_out = await service.upsert_product(ORG_ID, "Мука", unit="мешок")

        assert status_out == "created"

    async def test_upsert_merges_custom_fields(self, mock_session, mock_uow):
        existing = MagicMock()
        existing.custom_fields = {"origin": "altay"}
        existing.local_fields = {}
        mock_session.execute.return_value.scalar_one_or_none.return_value = existing
        mock_uow.eav_attributes.get_by_entity_code = AsyncMock(
            return_value=[
                EavAttribute(code="origin", name="Origin", field_type="string"),
                EavAttribute(code="organic", name="Organic", field_type="boolean"),
            ]
        )

        service = ProductService(mock_uow)
        _, status_out = await service.upsert_product(
            ORG_ID, "Мука", unit="кг", custom_fields={"organic": True}
        )

        assert status_out == "updated"
        assert existing.custom_fields == {"origin": "altay", "organic": True}


class TestProductRepositoryInvalidUuid:
    async def test_invalid_uuid_raises_not_found(self, mock_session):
        repo = ProductRepository(mock_session)
        with pytest.raises(NotFoundException):
            await repo.get_by_id_and_org("zzz", ORG_ID)
        mock_session.execute.assert_not_awaited()
