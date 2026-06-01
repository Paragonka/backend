"""Archive clients instead of hard deletion."""

import pytest_asyncio


@pytest_asyncio.fixture
async def user_org(client):
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "archivetest@test.com",
            "password": "Password123",
            "full_name": "Archive Tester",
            "consent_to_processing": True,
        },
    )
    user_data = reg.json()
    org = await client.post(
        "/api/v1/orgs",
        json={"name": "Archive Org"},
        headers={"Authorization": f"Bearer {user_data['access_token']}"},
    )
    return user_data, org.json()


def _auth(user_data) -> dict:
    return {"Authorization": f"Bearer {user_data['access_token']}"}


async def _create_client(client, user_data, org_data, **fields) -> dict:
    resp = await client.post(
        "/api/v1/clients",
        json={"name": "Архивный", "phone": "+79990001122", **fields},
        headers=_auth(user_data),
        params={"org_id": org_data["id"]},
    )
    assert resp.status_code == 201
    return resp.json()


class TestClientArchiving:
    async def test_delete_client_with_orders_archives_not_destroys(
        self, client, user_org
    ):
        user_data, org_data = user_org
        cl = await _create_client(
            client, user_data, org_data, name="С Заказами", surname="Тестов"
        )
        order = await client.post(
            "/api/v1/orders",
            json={"client_id": cl["id"]},
            headers=_auth(user_data),
            params={"org_id": org_data["id"]},
        )
        assert order.status_code == 201

        # DELETE → 204 (archiving)
        resp = await client.delete(
            f"/api/v1/clients/{cl['id']}",
            headers=_auth(user_data),
            params={"org_id": org_data["id"]},
        )
        assert resp.status_code == 204

        # The order remains intact and the archived client's name is resolved
        got_order = await client.get(
            f"/api/v1/orders/{order.json()['id']}",
            headers=_auth(user_data),
            params={"org_id": org_data["id"]},
        )
        assert got_order.status_code == 200
        assert got_order.json()["client_name"] == "С Заказами Тестов"

        # Hidden from the list by default
        listing = await client.get(
            "/api/v1/clients",
            headers=_auth(user_data),
            params={"org_id": org_data["id"]},
        )
        ids = [c["id"] for c in listing.json()["data"]]
        assert cl["id"] not in ids

        listing_all = await client.get(
            "/api/v1/clients/all",
            headers=_auth(user_data),
            params={"org_id": org_data["id"]},
        )
        assert all(c["id"] != cl["id"] for c in listing_all.json())

    async def test_get_archived_client_404_without_flag_200_with_flag(
        self, client, user_org
    ):
        user_data, org_data = user_org
        cl = await _create_client(client, user_data, org_data)
        await client.delete(
            f"/api/v1/clients/{cl['id']}",
            headers=_auth(user_data),
            params={"org_id": org_data["id"]},
        )

        hidden = await client.get(
            f"/api/v1/clients/{cl['id']}",
            headers=_auth(user_data),
            params={"org_id": org_data["id"]},
        )
        assert hidden.status_code == 404

        shown = await client.get(
            f"/api/v1/clients/{cl['id']}",
            headers=_auth(user_data),
            params={"org_id": org_data["id"], "include_archived": "true"},
        )
        assert shown.status_code == 200
        assert shown.json()["is_archived"] is True

    async def test_list_include_archived_true_shows_archived(self, client, user_org):
        user_data, org_data = user_org
        cl = await _create_client(client, user_data, org_data)
        await client.delete(
            f"/api/v1/clients/{cl['id']}",
            headers=_auth(user_data),
            params={"org_id": org_data["id"]},
        )
        listing = await client.get(
            "/api/v1/clients",
            headers=_auth(user_data),
            params={"org_id": org_data["id"], "include_archived": "true"},
        )
        ids = [c["id"] for c in listing.json()["data"]]
        assert cl["id"] in ids

    async def test_restore_makes_client_visible_again(self, client, user_org):
        user_data, org_data = user_org
        cl = await _create_client(client, user_data, org_data)
        await client.delete(
            f"/api/v1/clients/{cl['id']}",
            headers=_auth(user_data),
            params={"org_id": org_data["id"]},
        )

        restored = await client.post(
            f"/api/v1/clients/{cl['id']}/restore",
            headers=_auth(user_data),
            params={"org_id": org_data["id"]},
        )
        assert restored.status_code == 200
        body = restored.json()
        assert body["is_archived"] is False

        visible = await client.get(
            f"/api/v1/clients/{cl['id']}",
            headers=_auth(user_data),
            params={"org_id": org_data["id"]},
        )
        assert visible.status_code == 200

        listing = await client.get(
            "/api/v1/clients",
            headers=_auth(user_data),
            params={"org_id": org_data["id"]},
        )
        assert cl["id"] in [c["id"] for c in listing.json()["data"]]

    async def test_repeated_delete_idempotent_204(self, client, user_org):
        user_data, org_data = user_org
        cl = await _create_client(client, user_data, org_data)
        params = {"org_id": org_data["id"]}
        first = await client.delete(
            f"/api/v1/clients/{cl['id']}", headers=_auth(user_data), params=params
        )
        second = await client.delete(
            f"/api/v1/clients/{cl['id']}", headers=_auth(user_data), params=params
        )
        assert first.status_code == 204
        assert second.status_code == 204

    async def test_upsert_same_phone_creates_new_after_archive(
        self, client, user_org, test_session_factory
    ):
        user_data, org_data = user_org
        cl = await _create_client(client, user_data, org_data, phone="+70001112233")
        await client.delete(
            f"/api/v1/clients/{cl['id']}",
            headers=_auth(user_data),
            params={"org_id": org_data["id"]},
        )

        # An archived phone does not block deduplication: upsert creates a new client.
        from app.core.uow import AppUnitOfWork
        from app.features.clients.service import ClientService

        service = ClientService(AppUnitOfWork(test_session_factory))
        created, status_out = await service.upsert_client(
            str(org_data["id"]),
            name="Upsert после архива",
            phone="+70001112233",
        )
        assert status_out == "created"
        assert str(created.id) != cl["id"]

        listing = await client.get(
            "/api/v1/clients/all",
            headers=_auth(user_data),
            params={"org_id": org_data["id"], "include_archived": "true"},
        )
        active_with_phone = [
            c
            for c in listing.json()
            if c["phone"] == "+70001112233" and not c["is_archived"]
        ]
        assert len(active_with_phone) == 1

    async def test_restore_nonexistent_returns_404(self, client, user_org):
        user_data, org_data = user_org
        resp = await client.post(
            "/api/v1/clients/00000000-0000-0000-0000-000000000000/restore",
            headers=_auth(user_data),
            params={"org_id": org_data["id"]},
        )
        assert resp.status_code == 404
