import pytest_asyncio


@pytest_asyncio.fixture
async def user_org(client):
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "financestest@test.com",
            "password": "Password123",
            "full_name": "Test User",
            "consent_to_processing": True,
        },
    )
    user_data = reg.json()
    org = await client.post(
        "/api/v1/orgs",
        json={"name": "Finance Org"},
        headers={"Authorization": f"Bearer {user_data['access_token']}"},
    )
    org_data = org.json()
    return user_data, org_data


class TestFinanceAPI:
    async def test_summary_empty(self, client, user_org):
        user_data, org_data = user_org
        response = await client.get(
            "/api/v1/finances/summary",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert float(data["total_revenue"]) == 0
        assert float(data["total_expenses"]) == 0
        assert float(data["total_pnl"]) == 0
        assert len(data["monthly"]) == 12

    async def test_summary_with_data(self, client, user_org):
        user_data, org_data = user_org

        product_resp = await client.post(
            "/api/v1/products",
            json={"name": "Coffee", "price": 500.0, "product_type": "good"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        product = product_resp.json()

        order_resp = await client.post(
            "/api/v1/orders",
            json={"execution_date": "2026-05-15", "notes": "Test order"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        order = order_resp.json()
        order_id = order["id"]

        await client.post(
            f"/api/v1/orders/{order_id}/items",
            json={
                "product_id": product["id"],
                "name": "Coffee",
                "price": 500.0,
                "qty": 2,
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )

        await client.post(
            f"/api/v1/orders/{order_id}/status",
            json={"status": "done"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )

        await client.post(
            "/api/v1/receipts",
            json={
                "receipt_date": "2026-05-16",
                "items": [{"name": "Flour", "price": 100.0, "qty": 3}],
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )

        response = await client.get(
            "/api/v1/finances/summary",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert float(data["total_revenue"]) == 1000.0
        assert float(data["total_expenses"]) == 300.0
        assert float(data["total_pnl"]) == 700.0

        may_entry = [m for m in data["monthly"] if m["month"] == "2026-05"]
        assert len(may_entry) == 1
        assert float(may_entry[0]["revenue"]) == 1000.0
        assert float(may_entry[0]["expenses"]) == 300.0

    async def test_summary_date_range_buckets(self, client, user_org):
        user_data, org_data = user_org

        product_resp = await client.post(
            "/api/v1/products",
            json={"name": "Coffee", "price": 500.0, "product_type": "good"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        product = product_resp.json()

        # Order in the month just inside the range and one outside it
        for exec_date in ["2026-01-15", "2026-02-20", "2026-03-10", "2025-12-31"]:
            order_resp = await client.post(
                "/api/v1/orders",
                json={"execution_date": exec_date, "notes": "Test"},
                headers={"Authorization": f"Bearer {user_data['access_token']}"},
                params={"org_id": org_data["id"]},
            )
            order_id = order_resp.json()["id"]
            await client.post(
                f"/api/v1/orders/{order_id}/items",
                json={
                    "product_id": product["id"],
                    "name": "Coffee",
                    "price": 100.0,
                    "qty": 1,
                },
                headers={"Authorization": f"Bearer {user_data['access_token']}"},
                params={"org_id": org_data["id"]},
            )
            await client.post(
                f"/api/v1/orders/{order_id}/status",
                json={"status": "done"},
                headers={"Authorization": f"Bearer {user_data['access_token']}"},
                params={"org_id": org_data["id"]},
            )

        response = await client.get(
            "/api/v1/finances/summary",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={
                "org_id": org_data["id"],
                "date_from": "2026-01-15",
                "date_to": "2026-03-10",
            },
        )
        assert response.status_code == 200
        data = response.json()
        months = [m["month"] for m in data["monthly"]]
        assert months == ["2026-01", "2026-02", "2026-03"]
        assert data["from_month"] == "2026-01"
        assert data["to_month"] == "2026-03"
        # The Dec 2025 order must be excluded
        assert float(data["total_revenue"]) == 300.0

    async def test_summary_date_range_missing_one_param(self, client, user_org):
        user_data, org_data = user_org
        tok = user_data["access_token"]

        resp = await client.get(
            "/api/v1/finances/summary",
            headers={"Authorization": f"Bearer {tok}"},
            params={"org_id": org_data["id"], "date_from": "2026-01-15"},
        )
        assert resp.status_code == 400

        resp = await client.get(
            "/api/v1/finances/summary",
            headers={"Authorization": f"Bearer {tok}"},
            params={"org_id": org_data["id"], "date_to": "2026-03-10"},
        )
        assert resp.status_code == 400

    async def test_summary_date_range_invalid_format(self, client, user_org):
        user_data, org_data = user_org
        tok = user_data["access_token"]

        resp = await client.get(
            "/api/v1/finances/summary",
            headers={"Authorization": f"Bearer {tok}"},
            params={
                "org_id": org_data["id"],
                "date_from": "2026/01/15",
                "date_to": "2026-03-10",
            },
        )
        assert resp.status_code == 422

        resp = await client.get(
            "/api/v1/finances/summary",
            headers={"Authorization": f"Bearer {tok}"},
            params={
                "org_id": org_data["id"],
                "date_from": "not-a-date",
                "date_to": "2026-03-10",
            },
        )
        assert resp.status_code == 422

    async def test_summary_date_from_after_date_to(self, client, user_org):
        user_data, org_data = user_org
        tok = user_data["access_token"]

        resp = await client.get(
            "/api/v1/finances/summary",
            headers={"Authorization": f"Bearer {tok}"},
            params={
                "org_id": org_data["id"],
                "date_from": "2026-03-10",
                "date_to": "2026-01-15",
            },
        )
        assert resp.status_code == 400

    async def test_summary_months_regression(self, client, user_org):
        # months param alone must keep previous behavior
        user_data, org_data = user_org
        resp = await client.get(
            "/api/v1/finances/summary",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "months": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["monthly"]) == 3
