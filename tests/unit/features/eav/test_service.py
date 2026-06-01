from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.features.eav.models import EavAttribute
from app.features.eav.repository import EavAttributeRepository
from app.features.eav.service import EavAttributeService
from app.shared.exceptions import (
    ConflictException,
    EavValidationError,
    NotFoundException,
)

ORG_ID = "06a2502b-6534-7779-8000-4ff242017bf0"


class TestEavAttributeService:
    async def test_create_attribute_success(self, mock_session, mock_uow):
        async def refresh_side_effect(obj):
            obj.id = uuid4()

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        service = EavAttributeService(mock_uow)
        attr = await service.create_attribute(
            ORG_ID,
            "product",
            "tin",
            "ИНН",
            "string",
            True,
            "",
        )

        mock_session.add.assert_called()
        mock_session.flush.assert_awaited()
        assert attr.org_id == ORG_ID
        assert attr.entity_code == "product"
        assert attr.code == "tin"
        assert attr.name == "ИНН"
        assert attr.field_type == "string"
        assert attr.is_required is True

    async def test_create_attribute_defaults(self, mock_session, mock_uow):
        async def refresh_side_effect(obj):
            obj.id = uuid4()

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        service = EavAttributeService(mock_uow)
        attr = await service.create_attribute(ORG_ID, "product", "note", "Примечание")

        assert attr.field_type == "string"
        assert attr.is_required is False
        assert attr.default_value == ""

    async def test_create_duplicate_code_raises(self, mock_session, mock_uow):
        existing = MagicMock(spec=EavAttribute)
        mock_session.execute.return_value.scalar_one_or_none.return_value = existing

        service = EavAttributeService(mock_uow)
        with pytest.raises(ConflictException, match="already exists"):
            await service.create_attribute(ORG_ID, "product", "tin", "ИНН")

    async def test_create_invalid_field_type_raises(self, mock_session, mock_uow):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        service = EavAttributeService(mock_uow)
        with pytest.raises(EavValidationError, match="Invalid field_type"):
            await service.create_attribute(
                ORG_ID, "product", "bad", "Bad", field_type="unsupported"
            )

    async def test_get_by_entity_code(self, mock_session, mock_uow):
        attr1 = MagicMock(spec=EavAttribute)
        attr1.code = "tin"
        attr2 = MagicMock(spec=EavAttribute)
        attr2.code = "kpp"
        execute_result = MagicMock()
        execute_result.scalars.return_value.all.return_value = [attr1, attr2]
        mock_session.execute.return_value = execute_result

        service = EavAttributeService(mock_uow)
        attrs = await service.get_by_entity_code(ORG_ID, "product")

        assert len(attrs) == 2

    async def test_delete_existing_attribute(self, mock_session, mock_uow):
        attr = MagicMock(spec=EavAttribute)
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = attr
        mock_session.execute.return_value = execute_result

        service = EavAttributeService(mock_uow)
        result = await service.delete_attribute(uuid4())

        assert result is True
        mock_session.delete.assert_called_once_with(attr)

    async def test_delete_nonexistent_attribute(self, mock_session, mock_uow):
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = execute_result

        service = EavAttributeService(mock_uow)
        result = await service.delete_attribute(uuid4())

        assert result is False


class TestEavAttributeRepositoryInvalidUuid:
    async def test_invalid_uuid_raises_not_found(self, mock_session):
        repo = EavAttributeRepository(mock_session)
        with pytest.raises(NotFoundException):
            await repo.get_by_id("zzz")
        mock_session.execute.assert_not_awaited()


class TestEavValidation:
    def test_validate_required_field_present(self):
        attrs = [
            EavAttribute(code="tin", name="ИНН", field_type="string", is_required=True)
        ]
        EavAttributeService.validate_custom_fields({"tin": "12345"}, attrs)

    def test_validate_required_field_missing_raises(self):
        attrs = [
            EavAttribute(code="tin", name="ИНН", field_type="string", is_required=True)
        ]
        with pytest.raises(EavValidationError, match="required"):
            EavAttributeService.validate_custom_fields({}, attrs)

    def test_validate_required_field_empty_raises(self):
        attrs = [
            EavAttribute(code="tin", name="ИНН", field_type="string", is_required=True)
        ]
        with pytest.raises(EavValidationError, match="required"):
            EavAttributeService.validate_custom_fields({"tin": ""}, attrs)

    def test_validate_number_field_accepts_number(self):
        attrs = [EavAttribute(code="volume", name="Volume", field_type="number")]
        EavAttributeService.validate_custom_fields({"volume": "12.5"}, attrs)

    def test_validate_number_field_rejects_string(self):
        attrs = [EavAttribute(code="volume", name="Volume", field_type="number")]
        with pytest.raises(EavValidationError, match="must be a number"):
            EavAttributeService.validate_custom_fields({"volume": "abc"}, attrs)

    def test_validate_boolean_field_accepts_bool(self):
        attrs = [EavAttribute(code="active", name="Active", field_type="boolean")]
        EavAttributeService.validate_custom_fields({"active": True}, attrs)

    def test_validate_boolean_field_rejects_string(self):
        attrs = [EavAttribute(code="active", name="Active", field_type="boolean")]
        with pytest.raises(EavValidationError, match="must be a boolean"):
            EavAttributeService.validate_custom_fields({"active": "yes"}, attrs)

    def test_validate_optional_field_missing_ok(self):
        attrs = [
            EavAttribute(
                code="note", name="Note", field_type="string", is_required=False
            )
        ]
        EavAttributeService.validate_custom_fields({}, attrs)
