import uuid

import pytest_asyncio


@pytest_asyncio.fixture
async def user_org(client):
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "receiptstest@test.com",
            "password": "Password123",
            "full_name": "Test User",
            "consent_to_processing": True,
        },
    )
    user_data = reg.json()
    org = await client.post(
        "/api/v1/orgs",
        json={"name": "Receipts Org"},
        headers={"Authorization": f"Bearer {user_data['access_token']}"},
    )
    org_data = org.json()
    return user_data, org_data


@pytest_asyncio.fixture
async def product(client, user_org):
    user_data, org_data = user_org
    resp = await client.post(
        "/api/v1/products",
        json={"name": "Croissant", "price": 150.0, "product_type": "good"},
        headers={"Authorization": f"Bearer {user_data['access_token']}"},
        params={"org_id": org_data["id"]},
    )
    return resp.json(), user_org


async def register_other_org_user(client):
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "receiptsother@test.com",
            "password": "Password123",
            "full_name": "Other User",
            "consent_to_processing": True,
        },
    )
    user_data = reg.json()
    org = await client.post(
        "/api/v1/orgs",
        json={"name": "Other Receipts Org"},
        headers={"Authorization": f"Bearer {user_data['access_token']}"},
    )
    return user_data, org.json()


class TestReceiptAPI:
    async def test_create_receipt(self, client, user_org):
        user_data, org_data = user_org
        response = await client.post(
            "/api/v1/receipts",
            json={
                "receipt_date": "2026-06-07 14:00",
                "source": "manual",
                "notes": "Test receipt",
                "items": [
                    {"name": "Croissant", "price": 150.0, "qty": 2},
                    {"name": "Coffee", "price": 200.0, "qty": 1},
                ],
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 201
        data = response.json()
        assert float(data["total"]) == 500.0  # 300 + 200
        assert data["org_id"] == org_data["id"]
        assert data["source"] == "manual"
        assert data["notes"] == "Test receipt"

    async def test_create_receipt_empty_items_returns_422(self, client, user_org):
        user_data, org_data = user_org
        response = await client.post(
            "/api/v1/receipts",
            json={"items": []},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 422

    async def test_get_receipt(self, client, user_org):
        user_data, org_data = user_org
        create_resp = await client.post(
            "/api/v1/receipts",
            json={
                "receipt_date": "2026-06-07 14:00",
                "items": [{"name": "Croissant", "price": 150.0, "qty": 1}],
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        receipt_id = create_resp.json()["id"]
        response = await client.get(
            f"/api/v1/receipts/{receipt_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 200
        assert response.json()["id"] == receipt_id

    async def test_get_nonexistent_receipt_returns_404(self, client, user_org):
        user_data, org_data = user_org
        response = await client.get(
            "/api/v1/receipts/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 404

    async def test_list_receipts(self, client, user_org):
        user_data, org_data = user_org
        await client.post(
            "/api/v1/receipts",
            json={"items": [{"name": "Item 1", "price": 100.0, "qty": 1}]},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        await client.post(
            "/api/v1/receipts",
            json={"items": [{"name": "Item 2", "price": 200.0, "qty": 1}]},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        response = await client.get(
            "/api/v1/receipts",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2

    async def test_filter_receipts_by_source(self, client, user_org):
        user_data, org_data = user_org
        await client.post(
            "/api/v1/receipts",
            json={
                "source": "manual",
                "items": [{"name": "Item", "price": 100.0, "qty": 1}],
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        await client.post(
            "/api/v1/receipts",
            json={
                "source": "biedronka",
                "items": [{"name": "Item", "price": 100.0, "qty": 1}],
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        response = await client.get(
            "/api/v1/receipts",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "filter[source]": "manual"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["source"] == "manual"

    async def test_pagination(self, client, user_org):
        user_data, org_data = user_org
        for i in range(3):
            await client.post(
                "/api/v1/receipts",
                json={"items": [{"name": f"Item {i}", "price": 100.0, "qty": 1}]},
                headers={"Authorization": f"Bearer {user_data['access_token']}"},
                params={"org_id": org_data["id"]},
            )
        response = await client.get(
            "/api/v1/receipts",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "limit": 2},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["next_cursor"] is not None

    async def test_list_receipt_items(self, client, user_org):
        user_data, org_data = user_org
        create_resp = await client.post(
            "/api/v1/receipts",
            json={
                "items": [
                    {"name": "Croissant", "price": 150.0, "qty": 2},
                    {"name": "Coffee", "price": 200.0, "qty": 1},
                ],
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        receipt_id = create_resp.json()["id"]
        response = await client.get(
            f"/api/v1/receipts/{receipt_id}/items",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 200
        items = response.json()
        assert len(items) == 2

    async def test_delete_receipt(self, client, user_org):
        user_data, org_data = user_org
        create_resp = await client.post(
            "/api/v1/receipts",
            json={"items": [{"name": "Item", "price": 100.0, "qty": 1}]},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        receipt_id = create_resp.json()["id"]
        response = await client.delete(
            f"/api/v1/receipts/{receipt_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 204

        get_resp = await client.get(
            f"/api/v1/receipts/{receipt_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert get_resp.status_code == 404

    async def test_total_auto_calculated(self, client, user_org):
        user_data, org_data = user_org
        response = await client.post(
            "/api/v1/receipts",
            json={
                "items": [
                    {"name": "A", "price": 100.0, "qty": 3},
                    {"name": "B", "price": 50.0, "qty": 2},
                ],
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 201
        data = response.json()
        assert float(data["total"]) == 400.0  # 300 + 100

    async def test_all_endpoint(self, client, user_org):
        user_data, org_data = user_org
        await client.post(
            "/api/v1/receipts",
            json={"items": [{"name": "Item", "price": 100.0, "qty": 1}]},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        response = await client.get(
            "/api/v1/receipts/all",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 200
        assert len(response.json()) >= 1

    async def test_get_other_org_receipt_returns_404(self, client, user_org):
        owner_data, owner_org = user_org
        create_resp = await client.post(
            "/api/v1/receipts",
            json={
                "notes": "confidential",
                "items": [{"name": "TopSecret", "price": 99.0, "qty": 1}],
            },
            headers={"Authorization": f"Bearer {owner_data['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        receipt_id = create_resp.json()["id"]

        other_user, other_org = await register_other_org_user(client)
        response = await client.get(
            f"/api/v1/receipts/{receipt_id}",
            headers={"Authorization": f"Bearer {other_user['access_token']}"},
            params={"org_id": other_org["id"]},
        )
        assert response.status_code == 404

    async def test_list_items_of_other_org_receipt_returns_404(self, client, user_org):
        owner_data, owner_org = user_org
        create_resp = await client.post(
            "/api/v1/receipts",
            json={"items": [{"name": "TopSecret", "price": 99.0, "qty": 1}]},
            headers={"Authorization": f"Bearer {owner_data['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        receipt_id = create_resp.json()["id"]

        other_user, other_org = await register_other_org_user(client)
        response = await client.get(
            f"/api/v1/receipts/{receipt_id}/items",
            headers={"Authorization": f"Bearer {other_user['access_token']}"},
            params={"org_id": other_org["id"]},
        )
        assert response.status_code == 404

    async def test_delete_other_org_receipt_returns_404_and_owner_keeps_it(
        self, client, user_org
    ):
        owner_data, owner_org = user_org
        create_resp = await client.post(
            "/api/v1/receipts",
            json={
                "notes": "confidential",
                "items": [{"name": "TopSecret", "price": 99.0, "qty": 1}],
            },
            headers={"Authorization": f"Bearer {owner_data['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        receipt_id = create_resp.json()["id"]

        other_user, other_org = await register_other_org_user(client)

        get_resp = await client.get(
            f"/api/v1/receipts/{receipt_id}",
            headers={"Authorization": f"Bearer {other_user['access_token']}"},
            params={"org_id": other_org["id"]},
        )
        assert get_resp.status_code == 404

        items_resp = await client.get(
            f"/api/v1/receipts/{receipt_id}/items",
            headers={"Authorization": f"Bearer {other_user['access_token']}"},
            params={"org_id": other_org["id"]},
        )
        assert items_resp.status_code == 404

        delete_resp = await client.delete(
            f"/api/v1/receipts/{receipt_id}",
            headers={"Authorization": f"Bearer {other_user['access_token']}"},
            params={"org_id": other_org["id"]},
        )
        assert delete_resp.status_code == 404

        owner_get_resp = await client.get(
            f"/api/v1/receipts/{receipt_id}",
            headers={"Authorization": f"Bearer {owner_data['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert owner_get_resp.status_code == 200
        assert owner_get_resp.json()["notes"] == "confidential"


async def _register_other_receipts_user(client):
    email = f"receiptsh4_{uuid.uuid4().hex[:8]}@test.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123",
            "full_name": "H4 Other",
            "consent_to_processing": True,
        },
    )
    assert reg.status_code == 201, reg.text
    user_data = reg.json()
    org = await client.post(
        "/api/v1/orgs",
        json={"name": f"H4 Other Org {uuid.uuid4().hex[:4]}"},
        headers={"Authorization": f"Bearer {user_data['access_token']}"},
    )
    assert org.status_code == 201, org.text
    return user_data, org.json()


class TestCreateReceiptValidationH4:
    async def test_create_receipt_random_client_returns_422(self, client, user_org):
        user_data, org_data = user_org
        random_client_id = str(uuid.uuid4())
        resp = await client.post(
            "/api/v1/receipts",
            json={
                "client_id": random_client_id,
                "items": [{"name": "Croissant", "price": 100.0, "qty": 1}],
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert resp.status_code == 422, resp.text
        assert "detail" in resp.json()
        assert resp.status_code != 500

    async def test_create_receipt_random_order_returns_422(self, client, user_org):
        user_data, org_data = user_org
        random_order_id = str(uuid.uuid4())
        resp = await client.post(
            "/api/v1/receipts",
            json={
                "order_id": random_order_id,
                "items": [{"name": "Croissant", "price": 100.0, "qty": 1}],
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert resp.status_code == 422, resp.text
        assert "detail" in resp.json()

    async def test_create_receipt_other_org_client_returns_422(self, client, user_org):
        owner_user, owner_org = user_org
        other_user, other_org = await _register_other_receipts_user(client)
        c_resp = await client.post(
            "/api/v1/clients",
            json={"name": "OtherClient", "phone": "+79990003344"},
            headers={"Authorization": f"Bearer {other_user['access_token']}"},
            params={"org_id": other_org["id"]},
        )
        assert c_resp.status_code == 201, c_resp.text
        other_client_id = c_resp.json()["id"]

        resp = await client.post(
            "/api/v1/receipts",
            json={
                "client_id": other_client_id,
                "items": [{"name": "Croissant", "price": 100.0, "qty": 1}],
            },
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert resp.status_code == 422, resp.text
        assert "detail" in resp.json()

    async def test_create_receipt_other_org_order_returns_422(self, client, user_org):
        owner_user, owner_org = user_org
        other_user, other_org = await _register_other_receipts_user(client)
        o_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {other_user['access_token']}"},
            params={"org_id": other_org["id"]},
        )
        assert o_resp.status_code == 201, o_resp.text
        other_order_id = o_resp.json()["id"]

        resp = await client.post(
            "/api/v1/receipts",
            json={
                "order_id": other_order_id,
                "items": [{"name": "Croissant", "price": 100.0, "qty": 1}],
            },
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert resp.status_code == 422, resp.text
        assert "detail" in resp.json()


class TestReceiptsOrdering:
    async def test_all_and_filtered_sorted_newest_first(self, client, user_org):
        """/all and filtered lists use one id DESC ordering (uuid7)."""
        user_data, org_data = user_org
        auth = {"Authorization": f"Bearer {user_data['access_token']}"}
        params = {"org_id": org_data["id"]}

        ids = []
        for i in range(3):
            resp = await client.post(
                "/api/v1/receipts",
                json={"items": [{"name": f"Item {i}", "price": 100.0, "qty": 1}]},
                headers=auth,
                params=params,
            )
            assert resp.status_code == 201
            ids.append(resp.json()["id"])

        all_resp = await client.get("/api/v1/receipts/all", headers=auth, params=params)
        assert all_resp.status_code == 200
        assert [r["id"] for r in all_resp.json()] == list(reversed(ids))

        list_resp = await client.get("/api/v1/receipts", headers=auth, params=params)
        assert list_resp.status_code == 200
        assert [r["id"] for r in list_resp.json()["data"]] == list(reversed(ids))

    async def test_desc_pagination_cursor_walks_oldest(self, client, user_org):
        user_data, org_data = user_org
        auth = {"Authorization": f"Bearer {user_data['access_token']}"}
        params = {"org_id": org_data["id"]}
        created = []
        for i in range(3):
            resp = await client.post(
                "/api/v1/receipts",
                json={"items": [{"name": f"P{i}", "price": 10.0, "qty": 1}]},
                headers=auth,
                params=params,
            )
            created.append(resp.json()["id"])

        page1 = await client.get(
            "/api/v1/receipts", headers=auth, params={**params, "limit": 2}
        )
        data1 = page1.json()
        assert [r["id"] for r in data1["data"]] == [created[2], created[1]]
        assert data1["next_cursor"] == created[1]

        page2 = await client.get(
            "/api/v1/receipts",
            headers=auth,
            params={**params, "limit": 2, "cursor": data1["next_cursor"]},
        )
        data2 = page2.json()
        assert [r["id"] for r in data2["data"]] == [created[0]]
