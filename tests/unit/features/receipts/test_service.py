from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pydantic
import pytest

from app.features.receipts.schemas import ReceiptItemCreate
from app.features.receipts.service import ReceiptService
from app.shared.exceptions import ValidationException

ORG_ID = "06a2502b-6534-7779-8000-4ff242017bf0"


class TestReceiptService:
    async def test_create_receipt(self, mock_session, mock_uow):
        async def refresh_side_effect(obj):
            obj.id = uuid4()

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)

        service = ReceiptService(mock_uow)
        items = [
            ReceiptItemCreate(name="Croissant", price=Decimal("150"), qty=Decimal("2"))
        ]
        receipt = await service.create_receipt(
            ORG_ID,
            items_data=items,
            notes="Test receipt",
        )

        mock_session.add.assert_called()
        mock_session.flush.assert_awaited()
        assert receipt.org_id == ORG_ID
        assert receipt.total == Decimal("300")

    async def test_create_receipt_multiple_items(self, mock_session, mock_uow):
        async def refresh_side_effect(obj):
            obj.id = uuid4()

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)

        service = ReceiptService(mock_uow)
        items = [
            ReceiptItemCreate(name="Croissant", price=Decimal("150"), qty=Decimal("2")),
            ReceiptItemCreate(name="Coffee", price=Decimal("200"), qty=Decimal("1")),
        ]
        receipt = await service.create_receipt(
            ORG_ID,
            items_data=items,
            notes="Test",
        )

        assert receipt.total == Decimal("500")  # 300 + 200

    async def test_create_receipt_empty_items_raises(self, mock_session, mock_uow):
        service = ReceiptService(mock_uow)
        with pytest.raises(ValidationException, match="at least one item"):
            await service.create_receipt(ORG_ID, items_data=[])

    async def test_create_receipt_zero_price_raises(self, mock_session, mock_uow):
        with pytest.raises(pydantic.ValidationError, match="greater than 0"):
            ReceiptItemCreate(name="Free item", price=Decimal("0"), qty=Decimal("1"))

    async def test_create_receipt_negative_price_raises(self, mock_session, mock_uow):
        with pytest.raises(pydantic.ValidationError, match="greater than 0"):
            ReceiptItemCreate(name="Negative", price=Decimal("-10"), qty=Decimal("1"))

    async def test_create_receipt_zero_qty_raises(self, mock_session, mock_uow):
        with pytest.raises(pydantic.ValidationError, match="greater than 0"):
            ReceiptItemCreate(name="Zero qty", price=Decimal("100"), qty=Decimal("0"))

    async def test_product_id_valid_uuid_normalized(self, mock_session, mock_uow):
        pid = uuid4()
        item = ReceiptItemCreate(
            name="Linked", price=Decimal("100"), qty=Decimal("1"), product_id=str(pid)
        )

        assert item.product_id == str(pid)

    async def test_product_id_none_passes(self, mock_session, mock_uow):
        item = ReceiptItemCreate(
            name="Linked", price=Decimal("100"), qty=Decimal("1"), product_id=None
        )

        assert item.product_id is None

    async def test_product_id_empty_string_becomes_none(self, mock_session, mock_uow):
        item = ReceiptItemCreate(
            name="Linked", price=Decimal("100"), qty=Decimal("1"), product_id=""
        )

        assert item.product_id is None

    async def test_product_id_garbage_raises(self, mock_session, mock_uow):
        with pytest.raises(pydantic.ValidationError, match="product_id"):
            ReceiptItemCreate(
                name="Linked",
                price=Decimal("100"),
                qty=Decimal("1"),
                product_id="not-a-uuid",
            )

    async def test_get_org_receipts(self, mock_session, mock_uow):
        mock_receipt = MagicMock()
        execute_result = MagicMock()
        execute_result.scalars.return_value.all.return_value = [mock_receipt]
        mock_session.execute.return_value = execute_result

        service = ReceiptService(mock_uow)
        receipts = await service.get_org_receipts(ORG_ID)

        assert len(receipts) == 1

    async def test_delete_receipt_in_org(self, mock_session, mock_uow):
        receipt = MagicMock()
        receipt.id = uuid4()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = receipt
        empty_result = MagicMock()
        empty_result.scalars.return_value.all.return_value = []
        mock_session.execute.side_effect = [execute_result, empty_result]

        service = ReceiptService(mock_uow)
        result = await service.delete_receipt_in_org(str(receipt.id), ORG_ID)

        assert result is True
        mock_session.delete.assert_called_once_with(receipt)

    async def test_delete_nonexistent_receipt_in_org(self, mock_session, mock_uow):
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = execute_result

        service = ReceiptService(mock_uow)
        result = await service.delete_receipt_in_org(str(uuid4()), ORG_ID)

        assert result is False

    async def test_create_receipt_from_jpk_valid(self, mock_session, mock_uow):
        json_data = {
            "document": {
                "naglowek": {"dataJPK": "2026-08-01T10:00:00"},
                "podmiot1": {"NIP": "1234567890", "nazwaPod": "Biedronka"},
                "paragon": {
                    "pozycja": [
                        {"towar": {"nazwa": "Chleb", "brutto": 500, "ilosc": 1}}
                    ]
                },
            }
        }

        service = ReceiptService(mock_uow)
        receipt = await service.create_receipt_from_jpk(ORG_ID, json_data)

        assert receipt.org_id == ORG_ID
        assert receipt.total == Decimal("5.00")
        assert receipt.source == "jpk"
        assert receipt.receipt_date == "2026-08-01 10:00"
        assert receipt.notes == "JPK [layer2] Biedronka TIN:1234567890"
        assert receipt.raw_data == json_data
        mock_session.add.assert_called()

    async def test_create_receipt_from_jpk_invalid_raises(
        self, mock_session, mock_uow, monkeypatch
    ):
        from app.features.receipts.jpk_parser import JpkParseResult
        from app.features.receipts.service import ReceiptParseError

        result = JpkParseResult(
            format_detected="unknown", errors=["unrecognized JPK format"]
        )
        monkeypatch.setattr(
            "app.features.receipts.service.parse_jpk", lambda data: result
        )

        service = ReceiptService(mock_uow)
        with pytest.raises(ReceiptParseError) as exc_info:
            await service.create_receipt_from_jpk(ORG_ID, {"foo": "bar"})

        assert exc_info.value.message == "Не удалось распарсить чек"
        assert exc_info.value.details == ["unrecognized JPK format"]
        assert exc_info.value.format_detected == "unknown"

    async def test_create_receipt_from_jpk_empty_items_raises(
        self, mock_session, mock_uow, monkeypatch
    ):
        from app.features.receipts.jpk_parser import JpkParseResult
        from app.features.receipts.service import ReceiptParseError

        result = JpkParseResult(format_detected="layer2")
        monkeypatch.setattr(
            "app.features.receipts.service.parse_jpk", lambda data: result
        )

        service = ReceiptService(mock_uow)
        with pytest.raises(ReceiptParseError) as exc_info:
            await service.create_receipt_from_jpk(ORG_ID, {})

        assert exc_info.value.details == []
