import asyncio
import uuid

import pytest_asyncio


async def register_other_org_user(client):
    email = f"ordersother_{uuid.uuid4().hex[:8]}@test.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123",
            "full_name": "Other User",
            "consent_to_processing": True,
        },
    )
    assert reg.status_code == 201, reg.text
    user_data = reg.json()
    org = await client.post(
        "/api/v1/orgs",
        json={"name": f"Other Orders Org {uuid.uuid4().hex[:4]}"},
        headers={"Authorization": f"Bearer {user_data['access_token']}"},
    )
    assert org.status_code == 201, org.text
    return user_data, org.json()


@pytest_asyncio.fixture
async def user_org(client):
    email = f"orderstest_{uuid.uuid4().hex[:8]}@test.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123",
            "full_name": "Test User",
            "consent_to_processing": True,
        },
    )
    user_data = reg.json()
    org = await client.post(
        "/api/v1/orgs",
        json={"name": "Orders Org"},
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
    return resp.json(), org_data, user_data


class TestOrderAPI:
    async def test_create_order(self, client, user_org):
        user_data, org_data = user_org
        response = await client.post(
            "/api/v1/orders",
            json={"notes": "Test order"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "draft"
        assert data["org_id"] == org_data["id"]

    async def test_list_orders(self, client, user_org):
        user_data, org_data = user_org
        await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        response = await client.get(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["next_cursor"] is None

    async def test_filter_orders_by_status(self, client, user_org):
        user_data, org_data = user_org
        resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        order_id = resp.json()["id"]
        await client.post(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "done"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        response = await client.get(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "filter[status]": "done"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["status"] == "done"

    async def test_get_order(self, client, user_org):
        user_data, org_data = user_org
        create_resp = await client.post(
            "/api/v1/orders",
            json={"notes": "Test"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        order_id = create_resp.json()["id"]
        response = await client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 200

    async def test_add_item(self, client, product):
        prod, org_data, user_data = product
        order_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        order_id = order_resp.json()["id"]

        response = await client.post(
            f"/api/v1/orders/{order_id}/items",
            json={
                "product_id": prod["id"],
                "name": "Croissant",
                "price": 150.0,
                "qty": 2,
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Croissant"
        assert float(data["price"]) == 150.0
        assert float(data["qty"]) == 2

    async def test_list_items(self, client, product):
        prod, org_data, user_data = product
        order_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        order_id = order_resp.json()["id"]
        await client.post(
            f"/api/v1/orders/{order_id}/items",
            json={
                "product_id": prod["id"],
                "name": "Croissant",
                "price": 150.0,
                "qty": 1,
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        response = await client.get(
            f"/api/v1/orders/{order_id}/items",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 200
        assert len(response.json()) == 1

    async def test_remove_item_recalculates_total(self, client, product):
        prod, org_data, user_data = product
        order_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        order_id = order_resp.json()["id"]
        item_resp = await client.post(
            f"/api/v1/orders/{order_id}/items",
            json={
                "product_id": prod["id"],
                "name": "Croissant",
                "price": 150.0,
                "qty": 1,
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        item_id = item_resp.json()["id"]

        get_before = await client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert get_before.status_code == 200
        assert float(get_before.json()["total"]) == 150.0

        response = await client.delete(
            f"/api/v1/orders/{order_id}/items/{item_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 204

        get_after = await client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert get_after.status_code == 200
        assert float(get_after.json()["total"]) == 0.0
        assert get_after.json()["items"] == []

    async def test_change_status(self, client, user_org):
        user_data, org_data = user_org
        order_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        order_id = order_resp.json()["id"]
        response = await client.post(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "confirmed"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "confirmed"

    async def test_delete_order_returns_204(self, client, user_org):
        user_data, org_data = user_org
        create_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        order_id = create_resp.json()["id"]
        response = await client.delete(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 204

        # order should no longer appear in the default (non-deleted) list
        listing = await client.get(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert listing.status_code == 200
        assert len(listing.json()["data"]) == 0

    async def test_delete_nonexistent_order_returns_404(self, client, user_org):
        user_data, org_data = user_org
        response = await client.delete(
            "/api/v1/orders/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 404

    async def test_list_orders_excludes_deleted_by_default(self, client, user_org):
        user_data, org_data = user_org
        create_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        order_id = create_resp.json()["id"]
        await client.delete(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )

        default_resp = await client.get(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        include_resp = await client.get(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "include_deleted": "true"},
        )
        assert default_resp.status_code == 200
        assert include_resp.status_code == 200
        assert len(default_resp.json()["data"]) == 0
        assert len(include_resp.json()["data"]) == 1

    async def test_is_deleted_field_in_response(self, client, user_org):
        user_data, org_data = user_org
        # normal (non-deleted) order reports is_deleted=false
        create_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert create_resp.status_code == 201
        assert create_resp.json()["is_deleted"] is False

        # after soft delete the order is visible only with include_deleted and reports is_deleted=true  # noqa: E501
        order_id = create_resp.json()["id"]
        del_resp = await client.delete(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert del_resp.status_code == 204

        include_resp = await client.get(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "include_deleted": "true"},
        )
        assert include_resp.status_code == 200
        data = include_resp.json()["data"]
        assert len(data) == 1
        assert data[0]["id"] == order_id
        assert data[0]["is_deleted"] is True

        # single-order GET also reports is_deleted
        get_resp = await client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["is_deleted"] is True

    async def test_get_order_invalid_uuid_returns_422(self, client, user_org):
        user_data, org_data = user_org
        response = await client.get(
            "/api/v1/orders/zzz",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 422

    async def test_delete_order_invalid_uuid_returns_422(self, client, user_org):
        user_data, org_data = user_org
        response = await client.delete(
            "/api/v1/orders/zzz",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 422

    async def test_add_item_invalid_order_uuid_returns_422(self, client, user_org):
        user_data, org_data = user_org
        response = await client.post(
            "/api/v1/orders/zzz/items",
            json={"name": "Item", "price": 10.0, "qty": 1},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 422

    async def test_old_item_alias_route_removed(self, client, user_org):
        user_data, org_data = user_org
        response = await client.delete(
            "/api/v1/orders/items/00000000-0000-0000-0000-000000000001",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 404


class TestWriteOffAPI:
    async def test_writeoff_non_positive_qty_returns_422_and_stock_unchanged(
        self, client, user_org
    ):
        user_data, org_data = user_org
        prod_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "Flour",
                "price": 5.0,
                "product_type": "material",
                "stock_qty": 10,
                "track_inventory": True,
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert prod_resp.status_code == 201
        product = prod_resp.json()

        order_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        order_id = order_resp.json()["id"]
        item_resp = await client.post(
            f"/api/v1/orders/{order_id}/items",
            json={"product_id": product["id"], "name": "Flour", "price": 5.0, "qty": 1},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert item_resp.status_code == 201
        item = item_resp.json()

        for bad_qty in (0, -5):
            resp = await client.post(
                f"/api/v1/orders/{order_id}/write-offs",
                json={"order_item_id": item["id"], "qty": bad_qty},
                headers={"Authorization": f"Bearer {user_data['access_token']}"},
                params={"org_id": org_data["id"]},
            )
            assert resp.status_code == 422

        get_resp = await client.get(
            f"/api/v1/products/{product['id']}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert get_resp.status_code == 200
        assert float(get_resp.json()["stock_qty"]) == 10.0

    async def test_writeoff_insufficient_stock_returns_422_and_stock_unchanged(
        self, client, user_org
    ):
        user_data, org_data = user_org
        prod_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "Sugar",
                "price": 3.0,
                "product_type": "material",
                "stock_qty": 5,
                "track_inventory": True,
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert prod_resp.status_code == 201
        product = prod_resp.json()

        order_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        order_id = order_resp.json()["id"]
        item_resp = await client.post(
            f"/api/v1/orders/{order_id}/items",
            json={"product_id": product["id"], "name": "Sugar", "price": 3.0, "qty": 6},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert item_resp.status_code == 201
        item = item_resp.json()

        resp = await client.post(
            f"/api/v1/orders/{order_id}/write-offs",
            json={"order_item_id": item["id"], "qty": 6},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body.get("code") == "INSUFFICIENT_STOCK"

        get_resp = await client.get(
            f"/api/v1/products/{product['id']}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert get_resp.status_code == 200
        assert float(get_resp.json()["stock_qty"]) == 5.0


class TestOrderItemsIDOR:
    async def test_add_item_other_org_returns_404_and_order_unchanged(
        self, client, user_org
    ):
        owner_user, owner_org = user_org
        # create product in owner org
        prod_resp = await client.post(
            "/api/v1/products",
            json={"name": "Croissant", "price": 10.0, "product_type": "good"},
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert prod_resp.status_code == 201
        prod = prod_resp.json()

        order_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        order_id = order_resp.json()["id"]

        item_resp = await client.post(
            f"/api/v1/orders/{order_id}/items",
            json={
                "product_id": prod["id"],
                "name": "Croissant",
                "price": 10.0,
                "qty": 1,
            },
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert item_resp.status_code == 201

        # baseline total
        get_before = await client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert get_before.status_code == 200
        assert float(get_before.json()["total"]) == 10.0
        assert len(get_before.json()["items"]) == 1

        other_user, other_org = await register_other_org_user(client)

        # intruder tries to add item
        intruder_resp = await client.post(
            f"/api/v1/orders/{order_id}/items",
            json={
                "product_id": prod["id"],
                "name": "INTRUDER",
                "price": 666.0,
                "qty": 1,
            },
            headers={"Authorization": f"Bearer {other_user['access_token']}"},
            params={"org_id": other_org["id"]},
        )
        assert intruder_resp.status_code == 404

        # order unchanged
        get_after = await client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert get_after.status_code == 200
        assert float(get_after.json()["total"]) == 10.0
        assert len(get_after.json()["items"]) == 1
        assert get_after.json()["items"][0]["name"] == "Croissant"

        # also list items still correct
        list_resp = await client.get(
            f"/api/v1/orders/{order_id}/items",
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

    async def test_list_items_other_org_returns_404(self, client, user_org):
        owner_user, owner_org = user_org
        prod_resp = await client.post(
            "/api/v1/products",
            json={"name": "Croissant", "price": 10.0, "product_type": "good"},
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        prod = prod_resp.json()
        order_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        order_id = order_resp.json()["id"]
        await client.post(
            f"/api/v1/orders/{order_id}/items",
            json={
                "product_id": prod["id"],
                "name": "Croissant",
                "price": 10.0,
                "qty": 1,
            },
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        other_user, other_org = await register_other_org_user(client)
        resp = await client.get(
            f"/api/v1/orders/{order_id}/items",
            headers={"Authorization": f"Bearer {other_user['access_token']}"},
            params={"org_id": other_org["id"]},
        )
        assert resp.status_code == 404

    async def test_remove_item_other_org_returns_404_and_order_unchanged(
        self, client, user_org
    ):
        owner_user, owner_org = user_org
        prod_resp = await client.post(
            "/api/v1/products",
            json={"name": "Croissant", "price": 10.0, "product_type": "good"},
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        prod = prod_resp.json()
        order_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        order_id = order_resp.json()["id"]
        item_resp = await client.post(
            f"/api/v1/orders/{order_id}/items",
            json={
                "product_id": prod["id"],
                "name": "Croissant",
                "price": 10.0,
                "qty": 1,
            },
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        item_id = item_resp.json()["id"]

        other_user, other_org = await register_other_org_user(client)

        # foreign orderId -> 404
        del_resp = await client.delete(
            f"/api/v1/orders/{order_id}/items/{item_id}",
            headers={"Authorization": f"Bearer {other_user['access_token']}"},
            params={"org_id": other_org["id"]},
        )
        assert del_resp.status_code == 404

        # intruder's own orderId but foreign itemId -> 404
        own_order_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {other_user['access_token']}"},
            params={"org_id": other_org["id"]},
        )
        own_order_id = own_order_resp.json()["id"]
        del_resp2 = await client.delete(
            f"/api/v1/orders/{own_order_id}/items/{item_id}",
            headers={"Authorization": f"Bearer {other_user['access_token']}"},
            params={"org_id": other_org["id"]},
        )
        assert del_resp2.status_code == 404

        # owner still sees item and total
        get_resp = await client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert get_resp.status_code == 200
        assert float(get_resp.json()["total"]) == 10.0
        assert len(get_resp.json()["items"]) == 1

        list_resp = await client.get(
            f"/api/v1/orders/{order_id}/items",
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1

    async def test_add_item_nonexistent_product_returns_404(self, client, user_org):
        owner_user, owner_org = user_org
        order_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        order_id = order_resp.json()["id"]
        fake_pid = "00000000-0000-0000-0000-000000000999"
        resp = await client.post(
            f"/api/v1/orders/{order_id}/items",
            json={"product_id": fake_pid, "name": "Fake", "price": 5.0, "qty": 1},
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert resp.status_code == 404

        # ensure no items added
        get_resp = await client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert get_resp.status_code == 200
        assert float(get_resp.json()["total"]) == 0
        assert len(get_resp.json()["items"]) == 0

    async def test_add_item_product_from_other_org_returns_404(self, client, user_org):
        owner_user, owner_org = user_org
        other_user, other_org = await register_other_org_user(client)
        # product in other org
        prod_other_resp = await client.post(
            "/api/v1/products",
            json={"name": "OtherProd", "price": 20.0, "product_type": "good"},
            headers={"Authorization": f"Bearer {other_user['access_token']}"},
            params={"org_id": other_org["id"]},
        )
        assert prod_other_resp.status_code == 201
        prod_other = prod_other_resp.json()

        order_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        order_id = order_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/orders/{order_id}/items",
            json={
                "product_id": prod_other["id"],
                "name": "OtherProd",
                "price": 20.0,
                "qty": 1,
            },
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert resp.status_code == 404


class TestWriteOffIDOR:
    async def test_writeoff_foreign_order_returns_404_and_stock_unchanged(
        self, client, user_org
    ):
        owner_user, owner_org = user_org
        prod_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "Flour",
                "price": 5.0,
                "product_type": "material",
                "stock_qty": 100,
                "track_inventory": True,
            },
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert prod_resp.status_code == 201
        product = prod_resp.json()

        order_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        order_id = order_resp.json()["id"]
        item_resp = await client.post(
            f"/api/v1/orders/{order_id}/items",
            json={"product_id": product["id"], "name": "Flour", "price": 5.0, "qty": 1},
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert item_resp.status_code == 201
        item = item_resp.json()

        other_user, other_org = await register_other_org_user(client)

        # intruder addresses owner's order with his own org -> order not found
        resp = await client.post(
            f"/api/v1/orders/{order_id}/write-offs",
            json={"order_item_id": item["id"], "qty": 55},
            headers={"Authorization": f"Bearer {other_user['access_token']}"},
            params={"org_id": other_org["id"]},
        )
        assert resp.status_code == 404

        # stock unchanged for owner
        get_resp = await client.get(
            f"/api/v1/products/{product['id']}",
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert get_resp.status_code == 200
        assert float(get_resp.json()["stock_qty"]) == 100.0

    async def test_writeoff_foreign_order_item_returns_404(self, client, user_org):
        owner_user, owner_org = user_org
        # owner creates product+order+item
        prod_owner_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "OwnerMat",
                "price": 5.0,
                "product_type": "material",
                "stock_qty": 50,
                "track_inventory": True,
            },
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert prod_owner_resp.status_code == 201
        prod_owner = prod_owner_resp.json()

        order_owner_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        order_owner_id = order_owner_resp.json()["id"]

        item_owner_resp = await client.post(
            f"/api/v1/orders/{order_owner_id}/items",
            json={
                "product_id": prod_owner["id"],
                "name": "OwnerMat",
                "price": 5.0,
                "qty": 1,
            },
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert item_owner_resp.status_code == 201
        item_owner = item_owner_resp.json()

        other_user, other_org = await register_other_org_user(client)
        # intruder creates own product/order/item
        prod_intruder_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "IntruderMat",
                "price": 5.0,
                "product_type": "material",
                "stock_qty": 20,
                "track_inventory": True,
            },
            headers={"Authorization": f"Bearer {other_user['access_token']}"},
            params={"org_id": other_org["id"]},
        )
        assert prod_intruder_resp.status_code == 201
        prod_intruder = prod_intruder_resp.json()

        intruder_order_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {other_user['access_token']}"},
            params={"org_id": other_org["id"]},
        )
        intruder_order_id = intruder_order_resp.json()["id"]
        intruder_item_resp = await client.post(
            f"/api/v1/orders/{intruder_order_id}/items",
            json={
                "product_id": prod_intruder["id"],
                "name": "IntruderMat",
                "price": 5.0,
                "qty": 1,
            },
            headers={"Authorization": f"Bearer {other_user['access_token']}"},
            params={"org_id": other_org["id"]},
        )
        assert intruder_item_resp.status_code == 201
        intruder_item = intruder_item_resp.json()

        # intruder uses his own order but owner's item -> 404
        resp = await client.post(
            f"/api/v1/orders/{intruder_order_id}/write-offs",
            json={"order_item_id": item_owner["id"], "qty": 1},
            headers={"Authorization": f"Bearer {other_user['access_token']}"},
            params={"org_id": other_org["id"]},
        )
        assert resp.status_code == 404

        # owner uses his own order but intruder's item -> 404
        resp2 = await client.post(
            f"/api/v1/orders/{order_owner_id}/write-offs",
            json={"order_item_id": intruder_item["id"], "qty": 1},
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert resp2.status_code == 404

    async def test_writeoff_success_returns_writeoff_response(self, client, user_org):
        user_data, org_data = user_org
        prod_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "FlourSuccess",
                "price": 5.0,
                "product_type": "material",
                "stock_qty": 10,
                "track_inventory": True,
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert prod_resp.status_code == 201
        product = prod_resp.json()

        order_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        order_id = order_resp.json()["id"]
        item_resp = await client.post(
            f"/api/v1/orders/{order_id}/items",
            json={
                "product_id": product["id"],
                "name": "FlourSuccess",
                "price": 5.0,
                "qty": 1,
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert item_resp.status_code == 201
        item = item_resp.json()

        resp = await client.post(
            f"/api/v1/orders/{order_id}/write-offs",
            json={"order_item_id": item["id"], "qty": 3, "reason": "test reason"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["product_id"] == product["id"]
        assert float(data["qty"]) == 3.0
        assert data["reason"] == "test reason"
        assert "created_at" in data
        uuid.UUID(data["id"])
        uuid.UUID(data["product_id"])

        # stock decreased 10 -> 7
        get_resp = await client.get(
            f"/api/v1/products/{product['id']}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert get_resp.status_code == 200
        assert float(get_resp.json()["stock_qty"]) == 7.0


class TestCreateOrderClientValidationH4:
    async def test_create_order_random_client_returns_422(self, client, user_org):
        user_data, org_data = user_org
        random_client_id = str(uuid.uuid4())
        resp = await client.post(
            "/api/v1/orders",
            json={"client_id": random_client_id},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert resp.status_code == 422, resp.text
        body = resp.json()
        assert "detail" in body
        assert resp.status_code != 500

    async def test_create_order_other_org_client_returns_422(self, client, user_org):
        owner_user, owner_org = user_org
        other_user, other_org = await register_other_org_user(client)
        # create client in other org
        client_resp = await client.post(
            "/api/v1/clients",
            json={"name": "OtherOrgClient", "phone": "+79990001122"},
            headers={"Authorization": f"Bearer {other_user['access_token']}"},
            params={"org_id": other_org["id"]},
        )
        assert client_resp.status_code == 201, client_resp.text
        other_client_id = client_resp.json()["id"]

        resp = await client.post(
            "/api/v1/orders",
            json={"client_id": other_client_id},
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert resp.status_code == 422, resp.text
        body = resp.json()
        assert "detail" in body


class TestWriteOffStockRaceH6:
    async def test_concurrent_writeoffs_never_oversell(self, client, user_org):
        """20 concurrent write-offs of qty=1 against stock 10.

        Atomic conditional UPDATE must yield exactly 10 x 201, 10 x 422
        (INSUFFICIENT_STOCK) and final stock == 0 — no lost updates.
        """
        user_data, org_data = user_org
        prod_resp = await client.post(
            "/api/v1/products",
            json={
                "name": "RaceFlour",
                "price": 5.0,
                "product_type": "material",
                "stock_qty": 10,
                "track_inventory": True,
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert prod_resp.status_code == 201
        product = prod_resp.json()

        order_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        order_id = order_resp.json()["id"]
        # One write-off per order item is allowed (uq_write_offs_order_item);
        # create 20 distinct items so the stock race (10 in stock) is exercised
        # without hitting the double-write-off guard.
        item_ids: list[str] = []
        for i in range(20):
            item_resp = await client.post(
                f"/api/v1/orders/{order_id}/items",
                json={
                    "product_id": product["id"],
                    "name": f"RaceFlour-{i}",
                    "price": 5.0,
                    "qty": 1,
                },
                headers={"Authorization": f"Bearer {user_data['access_token']}"},
                params={"org_id": org_data["id"]},
            )
            assert item_resp.status_code == 201, item_resp.text
            item_ids.append(item_resp.json()["id"])

        auth = {"Authorization": f"Bearer {user_data['access_token']}"}
        params = {"org_id": org_data["id"]}

        async def do_writeoff(item_id: str) -> int:
            resp = await client.post(
                f"/api/v1/orders/{order_id}/write-offs",
                json={"order_item_id": item_id, "qty": 1},
                headers=auth,
                params=params,
            )
            assert resp.status_code in (201, 422), resp.text
            if resp.status_code == 422:
                assert resp.json().get("code") == "INSUFFICIENT_STOCK"
            return resp.status_code

        sem = asyncio.Semaphore(5)

        async def do_writeoff_limited(item_id: str) -> int:
            async with sem:
                return await do_writeoff(item_id)

        statuses = await asyncio.gather(*(do_writeoff_limited(iid) for iid in item_ids))
        created = statuses.count(201)
        rejected = statuses.count(422)

        # Invariant: total written off can never exceed initial stock.
        assert created <= 10
        assert created + rejected == 20
        # Integer qty=1 decrements make the outcome fully deterministic:
        # exactly 10 succeed, exactly 10 are rejected with INSUFFICIENT_STOCK.
        assert created == 10
        assert rejected == 10

        get_resp = await client.get(
            f"/api/v1/products/{product['id']}",
            headers=auth,
            params=params,
        )
        assert get_resp.status_code == 200
        assert float(get_resp.json()["stock_qty"]) == 0.0


class TestOrderEavCustomFields:
    async def _create_order_attr(self, client, user_org, **overrides):
        user_data, org_data = user_org
        payload = {
            "entity_code": "order",
            "code": "source",
            "name": "Источник",
            "field_type": "string",
        }
        payload.update(overrides)
        response = await client.post(
            "/api/v1/eav/attributes",
            json=payload,
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 201, response.text
        return response.json()

    async def test_create_order_with_valid_custom_fields(self, client, user_org):
        await self._create_order_attr(client, user_org)
        user_data, org_data = user_org
        response = await client.post(
            "/api/v1/orders",
            json={"notes": "Test order", "custom_fields": {"source": "instagram"}},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 201, response.text
        data = response.json()
        assert data["custom_fields"] == {"source": "instagram"}

    async def test_get_order_returns_custom_fields(self, client, user_org):
        await self._create_order_attr(client, user_org)
        user_data, org_data = user_org
        created = await client.post(
            "/api/v1/orders",
            json={"custom_fields": {"source": "call"}},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert created.status_code == 201, created.text
        order_id = created.json()["id"]

        fetched = await client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert fetched.status_code == 200
        assert fetched.json()["custom_fields"] == {"source": "call"}

    async def test_list_orders_returns_custom_fields(self, client, user_org):
        await self._create_order_attr(client, user_org)
        user_data, org_data = user_org
        await client.post(
            "/api/v1/orders",
            json={"custom_fields": {"source": "walkin"}},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        listed = await client.get(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert listed.status_code == 200
        data = listed.json()["data"]
        assert data[0]["custom_fields"] == {"source": "walkin"}

    async def test_create_order_unknown_code_returns_422(self, client, user_org):
        user_data, org_data = user_org
        response = await client.post(
            "/api/v1/orders",
            json={"custom_fields": {"not_defined": "x"}},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 422
        assert "not_defined" in response.json()["detail"]

    async def test_create_order_wrong_type_returns_422(self, client, user_org):
        await self._create_order_attr(
            client, user_org, code="qty", name="Кол-во", field_type="number"
        )
        user_data, org_data = user_org
        response = await client.post(
            "/api/v1/orders",
            json={"custom_fields": {"qty": "abc"}},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 422
        assert "qty" in response.json()["detail"]

    async def test_create_order_missing_required_returns_422(self, client, user_org):
        await self._create_order_attr(
            client, user_org, code="source", name="Источник", is_required=True
        )
        user_data, org_data = user_org
        response = await client.post(
            "/api/v1/orders",
            json={"custom_fields": {"source": ""}},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 422

    async def test_delete_order_attribute_cleans_custom_fields(self, client, user_org):
        attr = await self._create_order_attr(client, user_org)
        user_data, org_data = user_org
        headers = {"Authorization": f"Bearer {user_data['access_token']}"}
        params = {"org_id": org_data["id"]}
        created = await client.post(
            "/api/v1/orders",
            json={"custom_fields": {"source": "referral"}},
            headers=headers,
            params=params,
        )
        assert created.status_code == 201, created.text
        order_id = created.json()["id"]

        deleted = await client.delete(
            f"/api/v1/eav/attributes/{attr['id']}", headers=headers, params=params
        )
        assert deleted.status_code == 204

        fetched = await client.get(
            f"/api/v1/orders/{order_id}", headers=headers, params=params
        )
        assert fetched.status_code == 200
        assert fetched.json()["custom_fields"] == {}
