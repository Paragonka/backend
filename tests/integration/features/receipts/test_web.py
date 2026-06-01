"""Cross-tenant checks for the receipt HTMX layer (/app/{org_id}/receipts/...).

(web): loading/deleting a foreign receipt through HTML routes -> 404,
data remains intact.
"""

import uuid

import pytest_asyncio


@pytest_asyncio.fixture
async def owner_org(client):
    """User A + org A (receipt owner)."""
    email = f"receipts-web-{uuid.uuid4().hex[:8]}@test.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123",
            "full_name": "Web Owner",
            "consent_to_processing": True,
        },
    )
    user = reg.json()
    org = (
        await client.post(
            "/api/v1/orgs",
            json={"name": "Web Org A"},
            headers={"Authorization": f"Bearer {user['access_token']}"},
        )
    ).json()
    return user, org


@pytest_asyncio.fixture
async def stranger_org(client):
    """User B + org B (foreign tenant)."""
    email = f"receipts-web-other-{uuid.uuid4().hex[:8]}@test.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123",
            "full_name": "Web Stranger",
            "consent_to_processing": True,
        },
    )
    user = reg.json()
    org = (
        await client.post(
            "/api/v1/orgs",
            json={"name": "Web Org B"},
            headers={"Authorization": f"Bearer {user['access_token']}"},
        )
    ).json()
    return user, org


@pytest_asyncio.fixture
async def receipt(client, owner_org):
    user, org = owner_org
    resp = await client.post(
        "/api/v1/receipts",
        json={
            "receipt_date": "2026-08-24 10:00",
            "source": "manual",
            "notes": "confidential-web",
            "items": [{"name": "Croissant", "price": 99.0, "qty": 1}],
        },
        headers={"Authorization": f"Bearer {user['access_token']}"},
        params={"org_id": org["id"]},
    )
    assert resp.status_code == 201
    return resp.json()


class TestReceiptWebCrossTenant:
    async def test_detail_own_receipt_renders(self, client, owner_org, receipt):
        user, org = owner_org
        resp = await client.get(
            f"/app/{org['id']}/receipts/{receipt['id']}",
            headers={"Authorization": f"Bearer {user['access_token']}"},
        )
        assert resp.status_code == 200
        assert "confidential-web" in resp.text

    async def test_detail_foreign_receipt_returns_404(
        self, client, stranger_org, receipt
    ):
        stranger, stranger_org_data = stranger_org
        resp = await client.get(
            f"/app/{stranger_org_data['id']}/receipts/{receipt['id']}",
            headers={"Authorization": f"Bearer {stranger['access_token']}"},
        )
        assert resp.status_code == 404

    async def test_delete_foreign_receipt_returns_404_and_keeps_data(
        self, client, owner_org, stranger_org, receipt
    ):
        stranger, stranger_org_data = stranger_org
        owner, org = owner_org
        resp = await client.post(
            f"/app/{stranger_org_data['id']}/receipts/{receipt['id']}/delete",
            headers={"Authorization": f"Bearer {stranger['access_token']}"},
        )
        assert resp.status_code == 404
        # The owner's receipt remains untouched
        check = await client.get(
            f"/app/{org['id']}/receipts/{receipt['id']}",
            headers={"Authorization": f"Bearer {owner['access_token']}"},
        )
        assert check.status_code == 200
        assert "confidential-web" in check.text

    async def test_delete_own_receipt_redirects_and_removes(
        self, client, owner_org, receipt
    ):
        user, org = owner_org
        resp = await client.post(
            f"/app/{org['id']}/receipts/{receipt['id']}/delete",
            headers={"Authorization": f"Bearer {user['access_token']}"},
        )
        assert resp.status_code == 302
        assert resp.headers["location"] == f"/app/{org['id']}/receipts"
        gone = await client.get(
            f"/api/v1/receipts/{receipt['id']}",
            headers={"Authorization": f"Bearer {user['access_token']}"},
            params={"org_id": org["id"]},
        )
        assert gone.status_code == 404

    async def test_nonexistent_receipt_returns_404(self, client, owner_org):
        user, org = owner_org
        resp = await client.get(
            f"/app/{org['id']}/receipts/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {user['access_token']}"},
        )
        assert resp.status_code == 404
