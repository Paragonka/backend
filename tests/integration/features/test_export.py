import pytest
import pytest_asyncio

from app.core.config import settings

pytestmark = pytest.mark.skipif(
    not settings.feature_csv, reason="CSV disabled by feature-flag"
)


@pytest_asyncio.fixture
async def user_org(client):
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "exporttest@test.com",
            "password": "Password123",
            "full_name": "Test User",
            "consent_to_processing": True,
        },
    )
    user_data = reg.json()
    org = await client.post(
        "/api/v1/orgs",
        json={"name": "Export Org"},
        headers={"Authorization": f"Bearer {user_data['access_token']}"},
    )
    org_data = org.json()
    return user_data, org_data


class TestExportCsv:
    def _auth(self, user_data):
        return {"Authorization": f"Bearer {user_data['access_token']}"}

    async def test_export_clients_csv(self, client, user_org):
        user_data, org_data = user_org
        headers = self._auth(user_data)
        params = {"org_id": org_data["id"]}

        await client.post(
            "/api/v1/clients",
            json={"name": "Ivan", "surname": "Petrov", "phone": "+70001112233"},
            headers=headers,
            params=params,
        )
        resp = await client.get(
            "/api/v1/clients/export.csv", headers=headers, params=params
        )

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in resp.headers["content-disposition"]
        assert resp.headers["content-disposition"].endswith('"clients.csv"')
        text = resp.text
        assert text.startswith("\ufeff")
        assert "name,surname,phone,notes" in text
        assert "Ivan" in text
        assert "+70001112233" in text

    async def test_export_clients_csv_custom_fields_flattened(self, client, user_org):
        user_data, org_data = user_org
        headers = self._auth(user_data)
        params = {"org_id": org_data["id"]}
        csv_content = 'name,phone,custom_fields\nMaria,+70009998877,"{""card"": 42}"'

        await client.post(
            "/api/v1/clients/import",
            files={"file": ("c.csv", csv_content, "text/csv")},
            headers=headers,
            params=params,
        )
        resp = await client.get(
            "/api/v1/clients/export.csv", headers=headers, params=params
        )

        assert resp.status_code == 200
        text = resp.text
        assert "cf_card" in text
        assert "42" in text

    async def test_export_products_csv(self, client, user_org):
        user_data, org_data = user_org
        headers = self._auth(user_data)
        params = {"org_id": org_data["id"]}

        await client.post(
            "/api/v1/products",
            json={"name": "Croissant", "price": 150.0, "unit": "pcs"},
            headers=headers,
            params=params,
        )
        resp = await client.get(
            "/api/v1/products/export.csv", headers=headers, params=params
        )

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/csv; charset=utf-8"
        text = resp.text
        assert text.startswith("\ufeff")
        assert "name,category,unit,product_type,price" in text
        assert "Croissant" in text
        assert "pcs" in text

    async def test_export_orders_csv_one_row_per_item(self, client, user_org):
        user_data, org_data = user_org
        headers = self._auth(user_data)
        params = {"org_id": org_data["id"]}

        product = await client.post(
            "/api/v1/products",
            json={"name": "Croissant", "price": 150.0, "unit": "pcs"},
            headers=headers,
            params=params,
        )
        product_id = product.json()["id"]
        order = await client.post(
            "/api/v1/orders",
            json={"execution_date": "2026-07-31", "notes": "Bakery"},
            headers=headers,
            params=params,
        )
        order_id = order.json()["id"]
        for name, price, qty in [("Croissant", 150, 2), ("Кофе", 100, 1)]:
            await client.post(
                f"/api/v1/orders/{order_id}/items",
                json={
                    "product_id": product_id,
                    "name": name,
                    "price": price,
                    "qty": qty,
                },
                headers=headers,
                params=params,
            )

        resp = await client.get(
            "/api/v1/orders/export.csv", headers=headers, params=params
        )

        assert resp.status_code == 200
        text = resp.text
        assert text.startswith("\ufeff")
        assert "order_id,client_id,status,total,execution_date,notes" in text
        assert "item_name,item_price,item_qty" in text
        assert text.count("Croissant") == 1
        assert "Кофе" in text
        assert "Bakery" in text
        assert text.count("item_name") == 1
        assert text.count("\r\n") == 3

    async def test_export_receipts_csv_without_raw_data(self, client, user_org):
        user_data, org_data = user_org
        headers = self._auth(user_data)
        params = {"org_id": org_data["id"]}

        created = await client.post(
            "/api/v1/receipts",
            json={
                "receipt_date": "2026-07-31",
                "source": "egaistest",
                "notes": "Test",
                "raw_data": {"secret": "do-not-export"},
                "items": [{"name": "Croissant", "price": 617.28, "qty": 2}],
            },
            headers=headers,
            params=params,
        )
        assert created.status_code == 201
        resp = await client.get(
            "/api/v1/receipts/export.csv", headers=headers, params=params
        )

        assert resp.status_code == 200
        text = resp.text
        assert text.startswith("\ufeff")
        assert "client_id,order_id,receipt_date,total,source,notes" in text
        assert "1234.56" in text
        assert "secret" not in text
        assert "do-not-export" not in text

    async def test_export_other_org_forbidden(self, client, user_org):
        user_data, _ = user_org
        headers = self._auth(user_data)
        stranger_org = "00000000-0000-0000-0000-000000000000"

        resp = await client.get(
            "/api/v1/clients/export.csv",
            headers=headers,
            params={"org_id": stranger_org},
        )
        assert resp.status_code == 403

    async def test_product_export_reimport_round_trip(self, client, user_org):
        """Exported CSV must re-import cleanly (no 'Unknown columns', bool parsed)."""
        user_data, org_data = user_org
        headers = self._auth(user_data)
        params = {"org_id": org_data["id"]}

        await client.post(
            "/api/v1/products",
            json={
                "name": "Baguette",
                "price": 40.0,
                "unit": "pcs",
                "track_inventory": False,
            },
            headers=headers,
            params=params,
        )

        exported = await client.get(
            "/api/v1/products/export.csv", headers=headers, params=params
        )
        assert exported.status_code == 200
        csv_text = exported.text.lstrip("\ufeff")
        # Internal id must NOT be present in export.
        assert "id" not in csv_text.splitlines()[0].split(",")

        reimport = await client.post(
            "/api/v1/products/import",
            files={"file": ("products.csv", csv_text.encode("utf-8"), "text/csv")},
            headers=headers,
            params=params,
        )
        assert reimport.status_code == 200
        result = reimport.json()
        assert result["imported"] == 1
        assert len(result["errors"]) == 0

        # Round-trip bool parsing: the exported "False" string must import
        # back as False (Python bool("False") would wrongly yield True).
        listing = await client.get(
            "/api/v1/products/all", headers=headers, params=params
        )
        assert listing.status_code == 200
        reimported = [p for p in listing.json() if p["name"] == "Baguette"]
        assert len(reimported) == 2  # original + re-imported in "create" mode
        assert all(p["track_inventory"] is False for p in reimported)

    async def test_client_export_reimport_round_trip(self, client, user_org):
        user_data, org_data = user_org
        headers = self._auth(user_data)
        params = {"org_id": org_data["id"]}

        await client.post(
            "/api/v1/clients",
            json={"name": "Ivan", "surname": "Petrov", "phone": "+70001112233"},
            headers=headers,
            params=params,
        )

        exported = await client.get(
            "/api/v1/clients/export.csv", headers=headers, params=params
        )
        assert exported.status_code == 200
        csv_text = exported.text.lstrip("\ufeff")

        reimport = await client.post(
            "/api/v1/clients/import",
            files={"file": ("clients.csv", csv_text.encode("utf-8"), "text/csv")},
            headers=headers,
            params=params,
        )
        assert reimport.status_code == 200
        result = reimport.json()
        assert result["imported"] == 1
        assert len(result["errors"]) == 0
