from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.features.orgs.service import OrgService
from app.shared.exceptions import NotFoundException

USER_ID = "06a2502b-6534-7779-8000-4ff242017bf0"


class TestOrgServiceCreate:
    async def test_create_org_adds_member(self, mock_session, mock_uow):
        async def refresh_side_effect(obj):
            obj.id = uuid4()

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)

        service = OrgService(mock_uow)
        org = await service.create_org("My Bakery", USER_ID, "UTC")

        mock_session.add.assert_called()
        mock_session.flush.assert_awaited()
        assert org.name == "My Bakery"
        assert org.owner_id == USER_ID
        assert org.timezone == "UTC"

    async def test_create_org_default_timezone(self, mock_session, mock_uow):
        async def refresh_side_effect(obj):
            obj.id = uuid4()

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)

        service = OrgService(mock_uow)
        org = await service.create_org("Default TZ", USER_ID)

        assert org.timezone == "UTC"


class TestOrgServiceList:
    async def test_get_user_orgs_returns_list(self, mock_session, mock_uow):
        org1 = MagicMock()
        org1.name = "Bakery 1"
        org2 = MagicMock()
        org2.name = "Bakery 2"
        execute_result = MagicMock()
        execute_result.scalars.return_value.all.return_value = [org1, org2]
        mock_session.execute.return_value = execute_result

        service = OrgService(mock_uow)
        orgs = await service.get_user_orgs(USER_ID)

        assert len(orgs) == 2

    async def test_get_user_orgs_empty(self, mock_session, mock_uow):
        execute_result = MagicMock()
        execute_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = execute_result

        service = OrgService(mock_uow)
        orgs = await service.get_user_orgs(USER_ID)

        assert orgs == []


class TestOrgUpdate:
    async def test_update_org_renames(self, mock_session, mock_uow):
        org = MagicMock()
        org.name = "Old Name"
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = org
        mock_session.execute.return_value = execute_result

        service = OrgService(mock_uow)
        result = await service.update_org(USER_ID, "New Name")

        assert result is org
        assert org.name == "New Name"
        mock_session.flush.assert_awaited()

    async def test_update_org_missing_raises(self, mock_session, mock_uow):
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = execute_result

        service = OrgService(mock_uow)
        with pytest.raises(NotFoundException):
            await service.update_org(USER_ID, "New Name")


class TestOrgDelete:
    async def test_delete_org_calls_repository(self, mock_session, mock_uow):
        org = MagicMock()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = org
        mock_session.execute.return_value = execute_result
        mock_session.delete = AsyncMock()

        service = OrgService(mock_uow)
        await service.delete_org(USER_ID)

        mock_session.execute.assert_awaited()

    async def test_delete_org_missing_raises(self, mock_session, mock_uow):
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = execute_result

        service = OrgService(mock_uow)
        with pytest.raises(NotFoundException):
            await service.delete_org(USER_ID)


class TestOrgSettings:
    async def test_get_settings_returns_defaults_when_empty(
        self, mock_session, mock_uow
    ):
        execute_result = MagicMock()
        execute_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = execute_result

        service = OrgService(mock_uow)
        settings = await service.get_settings(USER_ID)

        assert settings == {"currency": "PLN"}

    async def test_get_settings_merges_stored_over_defaults(
        self, mock_session, mock_uow
    ):
        from app.features.orgs.models import OrganizationSetting

        setting = MagicMock(spec=OrganizationSetting)
        setting.key = "currency"
        setting.value = "EUR"

        execute_result = MagicMock()
        execute_result.scalars.return_value.all.return_value = [setting]
        mock_session.execute.return_value = execute_result

        service = OrgService(mock_uow)
        settings = await service.get_settings(USER_ID)

        assert settings == {"currency": "EUR"}

    async def test_update_settings_merges_and_upserts(self, mock_session, mock_uow):
        from app.features.orgs.models import OrganizationSetting

        setting = MagicMock(spec=OrganizationSetting)
        setting.key = "currency"
        setting.value = "PLN"
        setting.value = "PLN"

        execute_result = MagicMock()
        execute_result.scalars.return_value.all.return_value = [setting]
        mock_session.execute.return_value = execute_result

        service = OrgService(mock_uow)
        result = await service.update_settings(USER_ID, {"currency": "USD"})

        assert result == {"currency": "USD"}
