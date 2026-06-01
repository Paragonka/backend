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
            "email": "productstest@test.com",
            "password": "Password123",
            "full_name": "Test User",
            "consent_to_processing": True,
        },
    )
    user_data = reg.json()
    org = await client.post(
        "/api/v1/orgs",
        json={"name": "Products Org"},
        headers={"Authorization": f"Bearer {user_data['access_token']}"},
    )
    org_data = org.json()
    return user_data, org_data


class TestProductAPI:
    async def test_create_product(self, client, user_org):
        user_data, org_data = user_org
        response = await client.post(
            "/api/v1/products",
            json={
                "name": "Croissant",
                "price": 150.0,
                "unit": "шт",
                "product_type": "good",
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Croissant"
        assert float(data["price"]) == 150.0
        assert data["unit"] == "шт"
        assert data["product_type"] == "good"
        assert data["org_id"] == org_data["id"]
        assert data["is_sellable"] is True
        assert data["track_inventory"] is False
        assert data["stock_qty"] is None

    async def test_list_products(self, client, user_org):
        user_data, org_data = user_org
        await client.post(
            "/api/v1/products",
            json={"name": "Baguette", "price": 50.0},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        await client.post(
            "/api/v1/products",
            json={"name": "Brioche", "price": 80.0},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        response = await client.get(
            "/api/v1/products",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 2
        assert data["next_cursor"] is None

    async def test_filter_products(self, client, user_org):
        user_data, org_data = user_org
        await client.post(
            "/api/v1/products",
            json={"name": "Baguette", "product_type": "good", "price": 50.0},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        await client.post(
            "/api/v1/products",
            json={"name": "Sugar", "product_type": "material", "price": 10.0},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        response = await client.get(
            "/api/v1/products",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "filter[product_type]": "material"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["name"] == "Sugar"

    async def test_get_product(self, client, user_org):
        user_data, org_data = user_org
        create_resp = await client.post(
            "/api/v1/products",
            json={"name": "Sourdough", "price": 200.0},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        product_id = create_resp.json()["id"]

        response = await client.get(
            f"/api/v1/products/{product_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Sourdough"

    async def test_update_product(self, client, user_org):
        user_data, org_data = user_org
        create_resp = await client.post(
            "/api/v1/products",
            json={"name": "Old Name", "price": 100.0},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        product_id = create_resp.json()["id"]

        response = await client.put(
            f"/api/v1/products/{product_id}",
            json={"name": "New Name", "price": 150.0},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "New Name"

    async def test_delete_product(self, client, user_org):
        user_data, org_data = user_org
        create_resp = await client.post(
            "/api/v1/products",
            json={"name": "To Delete"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        product_id = create_resp.json()["id"]

        response = await client.delete(
            f"/api/v1/products/{product_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 204

    async def test_delete_product_with_order_items_returns_204(self, client, user_org):
        user_data, org_data = user_org
        create_resp = await client.post(
            "/api/v1/products",
            json={"name": "In Order", "price": 100.0},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        product_id = create_resp.json()["id"]

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
                "product_id": product_id,
                "name": "In Order",
                "price": 100.0,
                "qty": 1,
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert item_resp.status_code == 201

        response = await client.delete(
            f"/api/v1/products/{product_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 204

        # Order item is a snapshot: it survives with product_id set to NULL
        order_detail = await client.get(
            f"/api/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert order_detail.status_code == 200
        items = order_detail.json()["items"]
        assert len(items) == 1
        assert items[0]["product_id"] is None
        assert items[0]["name"] == "In Order"

        listing = await client.get(
            "/api/v1/products",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert listing.status_code == 200
        assert len(listing.json()["data"]) == 0

    async def test_delete_product_without_order_items_returns_204(
        self, client, user_org
    ):
        user_data, org_data = user_org
        create_resp = await client.post(
            "/api/v1/products",
            json={"name": "Standalone", "price": 50.0},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        product_id = create_resp.json()["id"]

        order_resp = await client.post(
            "/api/v1/orders",
            json={},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert order_resp.status_code == 201

        response = await client.delete(
            f"/api/v1/products/{product_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 204

    @csv_skip
    async def test_import_products_csv(self, client, user_org):
        user_data, org_data = user_org
        csv_content = (
            b"name,category,price,product_type\n"
            b"Flour,Base,50.0,material\nSugar,Base,30.0,material"
        )
        response = await client.post(
            "/api/v1/products/import",
            files={"file": ("products.csv", csv_content, "text/csv")},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 200
        result = response.json()
        assert result["imported"] == 2
        assert len(result["errors"]) == 0

    @csv_skip
    async def test_import_products_upsert_no_duplicates(self, client, user_org):
        user_data, org_data = user_org
        csv_content = (
            b"name,unit,price,product_type\nFlour,kg,50.0,good\nSugar,kg,30.0,good"
        )

        first = await client.post(
            "/api/v1/products/import",
            files={"file": ("p.csv", csv_content, "text/csv")},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "mode": "upsert"},
        )
        assert first.status_code == 200
        assert first.json()["created"] == 2
        assert first.json()["updated"] == 0

        second = await client.post(
            "/api/v1/products/import",
            files={"file": ("p.csv", csv_content, "text/csv")},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "mode": "upsert"},
        )
        assert second.status_code == 200
        assert second.json()["created"] == 0
        assert second.json()["updated"] == 2

        listing = await client.get(
            "/api/v1/products/all",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert len(listing.json()) == 2

    @csv_skip
    async def test_import_products_upsert_same_name_different_unit(
        self, client, user_org
    ):
        user_data, org_data = user_org
        csv_kg = b"name,unit,price,product_type\nFlour,kg,50.0,good"
        csv_bag = b"name,unit,price,product_type\nFlour,bag,500.0,good"

        resp = await client.post(
            "/api/v1/products/import",
            files={"file": ("p.csv", csv_kg, "text/csv")},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "mode": "upsert"},
        )
        assert resp.json()["created"] == 1

        resp = await client.post(
            "/api/v1/products/import",
            files={"file": ("p.csv", csv_bag, "text/csv")},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "mode": "upsert"},
        )
        assert resp.json()["created"] == 1

        listing = await client.get(
            "/api/v1/products/all",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert len(listing.json()) == 2

    @csv_skip
    async def test_import_products_upsert_invalid_custom_fields_error(
        self, client, user_org
    ):
        user_data, org_data = user_org
        csv_content = b"name,unit,custom_fields\nFlour,kg,not-json"

        resp = await client.post(
            "/api/v1/products/import",
            files={"file": ("p.csv", csv_content, "text/csv")},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "mode": "upsert"},
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["created"] == 0
        assert len(result["errors"]) == 1
        assert "custom_fields" in result["errors"][0]["error"]

    async def test_get_product_invalid_uuid_returns_422(self, client, user_org):
        user_data, org_data = user_org
        response = await client.get(
            "/api/v1/products/zzz",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 422

    async def test_put_product_invalid_uuid_returns_422(self, client, user_org):
        user_data, org_data = user_org
        response = await client.put(
            "/api/v1/products/zzz",
            json={"name": "New"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 422

    async def test_delete_product_invalid_uuid_returns_422(self, client, user_org):
        user_data, org_data = user_org
        response = await client.delete(
            "/api/v1/products/zzz",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 422
