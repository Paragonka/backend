from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.features.eav.models import EavAttribute
from app.features.orders.repository import OrderItemRepository, OrderRepository
from app.features.orders.service import OrderService
from app.shared.exceptions import EavValidationError, NotFoundException

ORG_ID = "06a2502b-6534-7779-8000-4ff242017bf0"


class TestOrderService:
    async def test_create_order(self, mock_session, mock_uow):
        async def refresh_side_effect(obj):
            obj.id = uuid4()
            obj.status = "draft"

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)

        service = OrderService(mock_uow)
        order = await service.create_order(ORG_ID, notes="Test order")

        mock_session.add.assert_called()
        mock_session.flush.assert_awaited()
        assert str(order.org_id) == ORG_ID
        assert order.status == "draft"

    async def test_get_org_orders(self, mock_session, mock_uow):
        mock_order = MagicMock()
        execute_result = MagicMock()
        execute_result.scalars.return_value.all.return_value = [mock_order]
        mock_session.execute.return_value = execute_result

        service = OrderService(mock_uow)
        orders = await service.get_org_orders(ORG_ID)

        assert len(orders) == 1

    async def test_add_item(self, mock_session, mock_uow):
        async def refresh_side_effect(obj):
            obj.id = uuid4()

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)
        # mock _recalc_total - get_items returns empty, get_by_id returns order
        mock_empty_result = MagicMock()
        mock_empty_result.scalars.return_value.all.return_value = []
        mock_order = MagicMock()
        mock_order_result = MagicMock()
        mock_order_result.scalar_one_or_none.return_value = mock_order
        mock_session.execute.side_effect = [mock_empty_result, mock_order_result]

        service = OrderService(mock_uow)
        order_id = uuid4()
        item = await service.add_item(
            order_id, str(uuid4()), "Croissant", Decimal("150.0"), Decimal(2)
        )

        assert item.name == "Croissant"
        assert item.price == 150.0
        assert item.qty == 2

    async def test_remove_item(self, mock_session, mock_uow):
        order_id = uuid4()
        order = MagicMock()
        order.id = order_id
        item = MagicMock()
        item.id = uuid4()
        item.order_id = str(order_id)
        order_result = MagicMock()
        order_result.scalar_one_or_none.return_value = order
        item_result = MagicMock()
        item_result.scalar_one_or_none.return_value = item
        mock_empty_result = MagicMock()
        mock_empty_result.scalars.return_value.all.return_value = []
        mock_session.execute.side_effect = [
            order_result,
            item_result,
            mock_empty_result,
            mock_empty_result,
            order_result,
        ]

        service = OrderService(mock_uow)
        await service.remove_item(order_id, uuid4(), org_id=ORG_ID)

        mock_session.delete.assert_called_once_with(item)

    async def test_remove_nonexistent_item_raises_not_found(
        self, mock_session, mock_uow
    ):
        order_id = uuid4()
        order = MagicMock()
        order.id = order_id
        order_result = MagicMock()
        order_result.scalar_one_or_none.return_value = order
        item_result = MagicMock()
        item_result.scalar_one_or_none.return_value = None
        mock_session.execute.side_effect = [order_result, item_result]

        service = OrderService(mock_uow)
        with pytest.raises(NotFoundException):
            await service.remove_item(order_id, uuid4(), org_id=ORG_ID)

    async def test_remove_item_foreign_order_raises_not_found(
        self, mock_session, mock_uow
    ):
        order_result = MagicMock()
        order_result.scalar_one_or_none.return_value = None
        mock_session.execute.side_effect = [order_result]

        service = OrderService(mock_uow)
        with pytest.raises(NotFoundException):
            await service.remove_item(uuid4(), uuid4(), org_id=ORG_ID)

        mock_session.delete.assert_not_called()

    async def test_change_status(self, mock_session, mock_uow):
        order = MagicMock()
        order.status = "draft"
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = order
        mock_session.execute.return_value = execute_result

        service = OrderService(mock_uow)
        result = await service.change_status(uuid4(), "confirmed")

        assert result is not None
        assert order.status == "confirmed"

    async def test_delete_order_sets_is_deleted(self, mock_session, mock_uow):
        order = MagicMock()
        order.is_deleted = False
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = order
        mock_session.execute.return_value = execute_result

        service = OrderService(mock_uow)
        updated_by = str(uuid4())
        result = await service.delete_order(uuid4(), updated_by=updated_by)

        assert result is True
        assert order.is_deleted is True
        assert order.updated_by == UUID(updated_by)
        mock_session.flush.assert_awaited()

    async def test_delete_nonexistent_order_returns_false(self, mock_session, mock_uow):
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = execute_result

        service = OrderService(mock_uow)
        result = await service.delete_order(uuid4())

        assert result is False


class TestOrderRepositoryInvalidUuid:
    async def test_invalid_order_uuid_raises_not_found(self, mock_session):
        repo = OrderRepository(mock_session)
        with pytest.raises(NotFoundException):
            await repo.get_by_id("zzz")
        mock_session.execute.assert_not_awaited()

    async def test_invalid_item_uuid_raises_not_found(self, mock_session):
        repo = OrderItemRepository(mock_session)
        with pytest.raises(NotFoundException):
            await repo.get_by_id("zzz")
        mock_session.execute.assert_not_awaited()


class TestOrderServiceEav:
    async def test_create_order_with_valid_custom_fields(self, mock_session, mock_uow):
        async def refresh_side_effect(obj):
            obj.id = uuid4()
            obj.status = "draft"

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)
        mock_uow.eav_attributes.get_by_entity_code = AsyncMock(
            return_value=[
                EavAttribute(code="delivery", name="Доставка", field_type="string"),
            ]
        )

        service = OrderService(mock_uow)
        order = await service.create_order(
            ORG_ID,
            notes="Test order",
            custom_fields={"delivery": "courier"},
        )

        mock_session.add.assert_called()
        assert str(order.org_id) == ORG_ID
        assert order.custom_fields == {"delivery": "courier"}

    async def test_create_order_without_custom_fields(self, mock_session, mock_uow):
        async def refresh_side_effect(obj):
            obj.id = uuid4()
            obj.status = "draft"

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)

        service = OrderService(mock_uow)
        order = await service.create_order(ORG_ID, notes="Test order")

        mock_session.add.assert_called()
        assert order.custom_fields == {}

    async def test_create_order_with_unknown_code_raises(self, mock_session, mock_uow):
        mock_uow.eav_attributes.get_by_entity_code = AsyncMock(return_value=[])

        service = OrderService(mock_uow)
        with pytest.raises(EavValidationError, match="Unknown attribute code"):
            await service.create_order(ORG_ID, custom_fields={"bogus": "x"})

    async def test_create_order_with_wrong_type_raises(self, mock_session, mock_uow):
        mock_uow.eav_attributes.get_by_entity_code = AsyncMock(
            return_value=[
                EavAttribute(code="qty", name="Qty", field_type="number"),
            ]
        )

        service = OrderService(mock_uow)
        with pytest.raises(EavValidationError, match="must be a number"):
            await service.create_order(ORG_ID, custom_fields={"qty": "abc"})

    async def test_create_order_missing_required_raises(self, mock_session, mock_uow):
        mock_uow.eav_attributes.get_by_entity_code = AsyncMock(
            return_value=[
                EavAttribute(
                    code="delivery",
                    name="Доставка",
                    field_type="string",
                    is_required=True,
                ),
            ]
        )

        service = OrderService(mock_uow)
        with pytest.raises(EavValidationError, match="required"):
            await service.create_order(ORG_ID, custom_fields={"delivery": ""})
