import pytest
import pytest_asyncio

from app.core.config import settings

csv_skip = pytest.mark.skipif(
    not settings.feature_csv, reason="CSV disabled by feature-flag"
)


@pytest_asyncio.fixture
async def user_org(client):
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "clientstest@test.com",
            "password": "Password123",
            "full_name": "Test User",
            "consent_to_processing": True,
        },
    )
    user_data = reg.json()
    org = await client.post(
        "/api/v1/orgs",
        json={"name": "Clients Org"},
        headers={"Authorization": f"Bearer {user_data['access_token']}"},
    )
    org_data = org.json()
    return user_data, org_data


class TestClientAPI:
    async def test_create_client_success(self, client, user_org):
        user_data, org_data = user_org
        response = await client.post(
            "/api/v1/clients",
            json={"name": "Иван", "surname": "Иванов", "phone": "+79991234567"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Иван"
        assert data["surname"] == "Иванов"
        assert data["phone"] == "+79991234567"
        assert data["org_id"] == org_data["id"]

    async def test_create_client_unauthorized(self, client):
        response = await client.post(
            "/api/v1/clients",
            json={"name": "No Auth"},
            params={"org_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert response.status_code == 401

    async def test_list_clients(self, client, user_org):
        user_data, org_data = user_org
        await client.post(
            "/api/v1/clients",
            json={"name": "Client A"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        await client.post(
            "/api/v1/clients",
            json={"name": "Client B"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        response = await client.get(
            "/api/v1/clients",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["next_cursor"] is None

    async def test_filter_clients(self, client, user_org):
        user_data, org_data = user_org
        await client.post(
            "/api/v1/clients",
            json={"name": "Иван", "surname": "Петров"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        await client.post(
            "/api/v1/clients",
            json={"name": "Петр", "surname": "Сидоров"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        response = await client.get(
            "/api/v1/clients",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "filter[name]": "Иван"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["name"] == "Иван"

    async def test_delete_client(self, client, user_org):
        user_data, org_data = user_org
        create_resp = await client.post(
            "/api/v1/clients",
            json={"name": "To Delete"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        client_id = create_resp.json()["id"]

        response = await client.delete(
            f"/api/v1/clients/{client_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 204

    @csv_skip
    async def test_import_clients_csv(self, client, user_org):
        user_data, org_data = user_org
        csv_content = (
            b"name,surname,phone\nTest,User,+70001112233\nAnother,Client,+70004445566"
        )
        response = await client.post(
            "/api/v1/clients/import",
            files={"file": ("clients.csv", csv_content, "text/csv")},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 200
        result = response.json()
        assert result["imported"] == 2
        assert len(result["errors"]) == 0

    @csv_skip
    async def test_import_clients_upsert_no_duplicates(self, client, user_org):
        user_data, org_data = user_org
        csv_content = (
            b"name,surname,phone\nTest,User,+70001112233\nAnother,Client,+70004445566"
        )

        first = await client.post(
            "/api/v1/clients/import",
            files={"file": ("clients.csv", csv_content, "text/csv")},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "mode": "upsert"},
        )
        assert first.status_code == 200
        assert first.json()["created"] == 2
        assert first.json()["updated"] == 0

        second = await client.post(
            "/api/v1/clients/import",
            files={"file": ("clients.csv", csv_content, "text/csv")},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "mode": "upsert"},
        )
        assert second.status_code == 200
        assert second.json()["created"] == 0
        assert second.json()["updated"] == 2

        listing = await client.get(
            "/api/v1/clients/all",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert len(listing.json()) == 2

    @csv_skip
    async def test_import_clients_upsert_updates_fields(self, client, user_org):
        user_data, org_data = user_org
        csv_old = b"name,surname,phone\nOld,Name,+70001112233"
        csv_new = b"name,surname,phone\nNew,Name,+70001112233"

        await client.post(
            "/api/v1/clients/import",
            files={"file": ("c.csv", csv_old, "text/csv")},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "mode": "upsert"},
        )

        resp = await client.post(
            "/api/v1/clients/import",
            files={"file": ("c.csv", csv_new, "text/csv")},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "mode": "upsert"},
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] == 1

        listing = await client.get(
            "/api/v1/clients/all",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        updated = next(c for c in listing.json() if c["phone"] == "+70001112233")
        assert updated["name"] == "New"
        assert updated["surname"] == "Name"

    @csv_skip
    async def test_import_clients_create_mode_allows_duplicates(self, client, user_org):
        user_data, org_data = user_org
        csv_content = b"name,surname,phone\nTest,User,+70001112233"

        for _ in range(2):
            resp = await client.post(
                "/api/v1/clients/import",
                files={"file": ("c.csv", csv_content, "text/csv")},
                headers={"Authorization": f"Bearer {user_data['access_token']}"},
                params={"org_id": org_data["id"]},
            )
            assert resp.status_code == 200
            assert resp.json()["created"] == 1

        listing = await client.get(
            "/api/v1/clients/all",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert len(listing.json()) == 2

    @csv_skip
    async def test_import_clients_upsert_other_org_403(self, client, user_org):
        user_data, _ = user_org
        csv_content = b"name,phone\nEvil,+70001112233"
        stranger_org = "00000000-0000-0000-0000-000000000000"

        resp = await client.post(
            "/api/v1/clients/import",
            files={"file": ("c.csv", csv_content, "text/csv")},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": stranger_org, "mode": "upsert"},
        )
        assert resp.status_code == 403

    async def test_get_client_invalid_uuid_returns_422(self, client, user_org):
        user_data, org_data = user_org
        response = await client.get(
            "/api/v1/clients/zzz",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 422

    async def test_put_client_invalid_uuid_returns_422(self, client, user_org):
        user_data, org_data = user_org
        response = await client.put(
            "/api/v1/clients/zzz",
            json={"name": "New"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 422

    async def test_delete_client_invalid_uuid_returns_422(self, client, user_org):
        user_data, org_data = user_org
        response = await client.delete(
            "/api/v1/clients/zzz",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 422


class TestClientOrders:
    async def test_returns_only_that_clients_orders_with_items(self, client, user_org):
        """Only the client's orders (scoped lookup) + items via a bulk query."""
        user_data, org_data = user_org
        auth = {"Authorization": f"Bearer {user_data['access_token']}"}
        params = {"org_id": org_data["id"]}

        p_resp = await client.post(
            "/api/v1/products",
            json={"name": "Kawa", "price": 10.0},
            headers=auth,
            params=params,
        )
        product_id = p_resp.json()["id"]

        c_a = await client.post(
            "/api/v1/clients",
            json={"name": "Anna", "surname": "A"},
            headers=auth,
            params=params,
        )
        c_b = await client.post(
            "/api/v1/clients",
            json={"name": "Borys", "surname": "B"},
            headers=auth,
            params=params,
        )
        client_a, client_b = c_a.json(), c_b.json()

        o1 = await client.post(
            "/api/v1/orders",
            json={"client_id": client_a["id"]},
            headers=auth,
            params=params,
        )
        o2 = await client.post(
            "/api/v1/orders",
            json={"client_id": client_b["id"]},
            headers=auth,
            params=params,
        )
        assert o1.status_code == 201
        assert o2.status_code == 201
        item = await client.post(
            f"/api/v1/orders/{o1.json()['id']}/items",
            json={"product_id": product_id, "name": "Kawa", "price": 10.0, "qty": 2},
            headers=auth,
            params=params,
        )
        assert item.status_code == 201

        resp = await client.get(
            f"/api/v1/clients/{client_a['id']}/orders", headers=auth, params=params
        )
        assert resp.status_code == 200
        orders = resp.json()
        assert [o["id"] for o in orders] == [o1.json()["id"]]
        assert orders[0]["client_name"] == "Anna A"
        assert len(orders[0]["items"]) == 1
        assert float(orders[0]["items"][0]["qty"]) == 2.0

    async def test_unknown_client_returns_404(self, client, user_org):
        import uuid

        user_data, org_data = user_org
        resp = await client.get(
            f"/api/v1/clients/{uuid.uuid4()}/orders",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert resp.status_code == 404


class TestClientSearchEscaping:
    async def test_percent_wildcard_in_filter_is_literal(self, client, user_org):
        """L1: searching for "50%" must not match "50x" (escape_like)."""
        user_data, org_data = user_org
        auth = {"Authorization": f"Bearer {user_data['access_token']}"}
        params = {"org_id": org_data["id"]}
        for name in ("50%", "50x", "500"):
            resp = await client.post(
                "/api/v1/clients",
                json={"name": name},
                headers=auth,
                params=params,
            )
            assert resp.status_code == 201

        resp = await client.get(
            "/api/v1/clients",
            headers=auth,
            params={**params, "filter[name]": "50%"},
        )
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()["data"]]
        assert names == ["50%"]

    async def test_underscore_wildcard_in_filter_is_literal(self, client, user_org):
        user_data, org_data = user_org
        auth = {"Authorization": f"Bearer {user_data['access_token']}"}
        params = {"org_id": org_data["id"]}
        for name in ("a_b", "axb"):
            resp = await client.post(
                "/api/v1/clients",
                json={"name": name},
                headers=auth,
                params=params,
            )
            assert resp.status_code == 201

        resp = await client.get(
            "/api/v1/clients",
            headers=auth,
            params={**params, "filter[name]": "a_b"},
        )
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()["data"]]
        assert names == ["a_b"]
