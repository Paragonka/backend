from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.features.clients.repository import ClientRepository
from app.features.clients.service import ClientService
from app.features.eav.models import EavAttribute
from app.shared.exceptions import NotFoundException

ORG_ID = "06a2502b-6534-7779-8000-4ff242017bf0"


class TestClientServiceCreate:
    async def test_create_client_success(self, mock_session, mock_uow):
        async def refresh_side_effect(obj):
            obj.id = uuid4()

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)

        service = ClientService(mock_uow)
        client = await service.create_client(ORG_ID, "Иван", "Иванов", "+7999")

        mock_session.add.assert_called()
        mock_session.flush.assert_awaited()
        assert client.name == "Иван"
        assert client.surname == "Иванов"
        assert client.phone == "+7999"
        assert client.org_id == ORG_ID

    async def test_create_client_minimal(self, mock_session, mock_uow):
        async def refresh_side_effect(obj):
            obj.id = uuid4()

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)

        service = ClientService(mock_uow)
        client = await service.create_client(ORG_ID, "Минимальный")

        assert client.name == "Минимальный"
        assert client.surname == ""
        assert client.phone == ""


class TestClientServiceList:
    async def test_get_org_clients_returns_list(self, mock_session, mock_uow):
        client1 = MagicMock()
        client1.name = "Client 1"
        client2 = MagicMock()
        client2.name = "Client 2"
        execute_result = MagicMock()
        execute_result.scalars.return_value.all.return_value = [client1, client2]
        mock_session.execute.return_value = execute_result

        service = ClientService(mock_uow)
        clients = await service.get_org_clients(ORG_ID)

        assert len(clients) == 2

    async def test_get_org_clients_empty(self, mock_session, mock_uow):
        execute_result = MagicMock()
        execute_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = execute_result

        service = ClientService(mock_uow)
        clients = await service.get_org_clients(ORG_ID)

        assert clients == []


class TestClientServiceFilter:
    async def test_get_filtered_no_filters(self, mock_session, mock_uow):
        client1 = MagicMock()
        client1.id = uuid4()
        client1.name = "Client 1"
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = [client1]
        mock_session.execute.side_effect = [count_result, items_result]

        service = ClientService(mock_uow)
        clients, next_cursor, total = await service.get_filtered(ORG_ID)

        assert len(clients) == 1
        assert next_cursor is None
        assert total == 1


class TestClientServiceArchive:
    async def test_archive_existing_client_sets_flag(self, mock_session, mock_uow):
        client = MagicMock()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = client
        mock_session.execute.return_value = execute_result

        service = ClientService(mock_uow)
        result = await service.archive_client(uuid4(), ORG_ID)

        assert result is client
        assert client.is_archived is True
        mock_session.delete.assert_not_called()
        mock_session.flush.assert_awaited()

    async def test_archive_nonexistent_client(self, mock_session, mock_uow):
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = execute_result

        service = ClientService(mock_uow)
        result = await service.archive_client(uuid4(), ORG_ID)

        assert result is None

    async def test_restore_existing_client_clears_flag(self, mock_session, mock_uow):
        client = MagicMock()
        client.is_archived = True
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = client
        mock_session.execute.return_value = execute_result

        service = ClientService(mock_uow)
        result = await service.restore_client(uuid4(), ORG_ID)

        assert result is client
        assert client.is_archived is False

    async def test_restore_nonexistent_client(self, mock_session, mock_uow):
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = execute_result

        service = ClientService(mock_uow)
        result = await service.restore_client(uuid4(), ORG_ID)

        assert result is None


class TestClientServiceVisible:
    async def test_get_client_visible_active_returns_client(
        self, mock_session, mock_uow
    ):
        client = MagicMock()
        client.is_archived = False
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = client
        mock_session.execute.return_value = execute_result

        service = ClientService(mock_uow)
        result = await service.get_client_visible(uuid4(), ORG_ID)

        assert result is client

    async def test_get_client_visible_archived_hidden_without_flag(
        self, mock_session, mock_uow
    ):
        client = MagicMock()
        client.is_archived = True
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = client
        mock_session.execute.return_value = execute_result

        service = ClientService(mock_uow)
        result = await service.get_client_visible(uuid4(), ORG_ID)

        assert result is None

    async def test_get_client_visible_archived_shown_with_flag(
        self, mock_session, mock_uow
    ):
        client = MagicMock()
        client.is_archived = True
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = client
        mock_session.execute.return_value = execute_result

        service = ClientService(mock_uow)
        result = await service.get_client_visible(
            uuid4(), ORG_ID, include_archived=True
        )

        assert result is client

    async def test_get_client_visible_nonexistent_returns_none(
        self, mock_session, mock_uow
    ):
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = execute_result

        service = ClientService(mock_uow)
        result = await service.get_client_visible(uuid4(), ORG_ID)

        assert result is None


class TestClientServiceUpdateInOrg:
    async def test_update_in_org_applies_fields(self, mock_session, mock_uow):
        client = MagicMock()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = client
        mock_session.execute.return_value = execute_result

        service = ClientService(mock_uow)
        result = await service.update_client_in_org(
            uuid4(),
            ORG_ID,
            name="Иван",
            surname="Петров",
            phone="+7999",
            notes="<b>hi</b>",
        )

        assert result is client
        assert client.name == "Иван"
        assert client.surname == "Петров"
        assert client.phone == "+7999"
        assert client.notes == "hi"
        mock_session.flush.assert_awaited()
        mock_session.refresh.assert_awaited()

    async def test_update_in_org_nonexistent_returns_none(self, mock_session, mock_uow):
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = execute_result

        service = ClientService(mock_uow)
        result = await service.update_client_in_org(uuid4(), ORG_ID, name="Иван")

        assert result is None
        mock_session.flush.assert_not_awaited()

    async def test_update_in_org_foreign_org_returns_none(self, mock_session, mock_uow):
        """Composite (org_id, id): a client of another org is never mutated."""
        execute_result = MagicMock()
        execute_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = execute_result

        service = ClientService(mock_uow)
        result = await service.update_client_in_org(
            uuid4(), "99999999-9999-9999-9999-999999999999", name="Чужой"
        )

        assert result is None
        mock_session.flush.assert_not_awaited()


class TestClientRepositoryInvalidUuid:
    async def test_invalid_uuid_raises_not_found(self, mock_session):
        repo = ClientRepository(mock_session)
        with pytest.raises(NotFoundException):
            await repo.get_by_id("zzz")
        mock_session.execute.assert_not_awaited()


class TestClientServiceUpsert:
    async def test_upsert_creates_when_no_phone_match(self, mock_session, mock_uow):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        async def refresh_side_effect(obj):
            obj.id = uuid4()

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)

        service = ClientService(mock_uow)
        client, status_out = await service.upsert_client(
            ORG_ID, "Иван", phone="+79990001122"
        )

        mock_session.add.assert_called()
        assert status_out == "created"
        assert client.name == "Иван"
        assert client.phone == "+79990001122"

    async def test_upsert_updates_existing_by_phone(self, mock_session, mock_uow):
        existing = MagicMock()
        existing.custom_fields = {}
        existing.local_fields = {}
        mock_session.execute.return_value.scalar_one_or_none.return_value = existing

        service = ClientService(mock_uow)
        client, status_out = await service.upsert_client(
            ORG_ID, "Иван Обновлённый", phone="+79990001122", notes="постоянный"
        )

        assert status_out == "updated"
        assert existing.name == "Иван Обновлённый"
        assert existing.notes == "постоянный"
        assert client is existing

    async def test_upsert_empty_phone_always_creates(self, mock_session, mock_uow):
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        async def refresh_side_effect(obj):
            obj.id = uuid4()

        mock_session.refresh = AsyncMock(side_effect=refresh_side_effect)

        service = ClientService(mock_uow)
        _, status_out = await service.upsert_client(ORG_ID, "Без телефона")

        assert status_out == "created"
        mock_session.add.assert_called()

    async def test_upsert_merges_custom_fields(self, mock_session, mock_uow):
        existing = MagicMock()
        existing.custom_fields = {"instagram": "@ivan"}
        existing.local_fields = {}
        mock_session.execute.return_value.scalar_one_or_none.return_value = existing
        mock_uow.eav_attributes.get_by_entity_code = AsyncMock(
            return_value=[
                EavAttribute(code="instagram", name="Instagram", field_type="string"),
                EavAttribute(code="loyalty", name="Loyalty", field_type="string"),
            ]
        )

        service = ClientService(mock_uow)
        _, status_out = await service.upsert_client(
            ORG_ID, "Иван", phone="+79990001122", custom_fields={"loyalty": "gold"}
        )

        assert status_out == "updated"
        assert existing.custom_fields == {"instagram": "@ivan", "loyalty": "gold"}
