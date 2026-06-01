import pytest_asyncio


@pytest_asyncio.fixture
async def user_a(client):
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "usera@test.com",
            "password": "Password123",
            "full_name": "User A",
            "consent_to_processing": True,
        },
    )
    return reg.json()


@pytest_asyncio.fixture
async def user_b(client):
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "userb@test.com",
            "password": "Password123",
            "full_name": "User B",
            "consent_to_processing": True,
        },
    )
    return reg.json()


class TestOrgCreate:
    async def test_create_org_success(self, client, user_a):
        response = await client.post(
            "/api/v1/orgs",
            json={"name": "My Bakery", "timezone": "UTC"},
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Bakery"
        assert data["timezone"] == "UTC"
        assert data["owner_id"] == user_a["user"]["id"]

    async def test_create_org_unauthorized(self, client):
        response = await client.post(
            "/api/v1/orgs",
            json={"name": "No Auth Bakery"},
        )
        assert response.status_code == 401


class TestOrgList:
    async def test_list_user_orgs(self, client, user_a):
        await client.post(
            "/api/v1/orgs",
            json={"name": "Bakery 1"},
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        await client.post(
            "/api/v1/orgs",
            json={"name": "Bakery 2"},
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        response = await client.get(
            "/api/v1/orgs",
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        assert response.status_code == 200
        orgs = response.json()
        assert len(orgs) >= 2

    async def test_list_orgs_empty_for_new_user(self, client, user_b):
        response = await client.get(
            "/api/v1/orgs",
            headers={"Authorization": f"Bearer {user_b['access_token']}"},
        )
        assert response.status_code == 200
        assert response.json() == []


class TestOrgIsolation:
    async def test_user_cannot_access_other_users_org(self, client, user_a, user_b):
        org_a = await client.post(
            "/api/v1/orgs",
            json={"name": "A's Org"},
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        org_id = org_a.json()["id"]

        response = await client.get(
            f"/api/v1/orgs/{org_id}",
            headers={"Authorization": f"Bearer {user_b['access_token']}"},
        )
        assert response.status_code == 403

    async def test_user_can_access_own_org(self, client, user_a):
        org = await client.post(
            "/api/v1/orgs",
            json={"name": "Own Org"},
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        org_id = org.json()["id"]

        response = await client.get(
            f"/api/v1/orgs/{org_id}",
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Own Org"

    async def test_nonexistent_org_id_returns_403(self, client, user_a):
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.get(
            f"/api/v1/orgs/{fake_id}",
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        assert response.status_code == 403


class TestOrgSettings:
    async def test_get_settings_default(self, client, user_a):
        org_resp = await client.post(
            "/api/v1/orgs",
            json={"name": "Settings Test"},
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        org_id = org_resp.json()["id"]

        response = await client.get(
            f"/api/v1/orgs/{org_id}/settings",
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        assert response.status_code == 200
        assert response.json() == {"currency": "PLN"}

    async def test_update_settings(self, client, user_a):
        org_resp = await client.post(
            "/api/v1/orgs",
            json={"name": "Update Settings Test"},
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        org_id = org_resp.json()["id"]

        put_resp = await client.put(
            f"/api/v1/orgs/{org_id}/settings",
            json={"currency": "EUR"},
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        assert put_resp.status_code == 200
        assert put_resp.json() == {"currency": "EUR"}

        get_resp = await client.get(
            f"/api/v1/orgs/{org_id}/settings",
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        assert get_resp.json() == {"currency": "EUR"}

    async def test_settings_org_isolation(self, client, user_a, user_b):
        org_a_resp = await client.post(
            "/api/v1/orgs",
            json={"name": "A's Org Settings"},
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        org_a_id = org_a_resp.json()["id"]

        await client.put(
            f"/api/v1/orgs/{org_a_id}/settings",
            json={"currency": "USD"},
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )

        response = await client.get(
            f"/api/v1/orgs/{org_a_id}/settings",
            headers={"Authorization": f"Bearer {user_b['access_token']}"},
        )
        assert response.status_code == 403


class TestOrgRename:
    async def test_owner_renames_org(self, client, user_a):
        org_resp = await client.post(
            "/api/v1/orgs",
            json={"name": "Old Bakery"},
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        org_id = org_resp.json()["id"]

        patch_resp = await client.patch(
            f"/api/v1/orgs/{org_id}",
            json={"name": "New Bakery"},
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["name"] == "New Bakery"

        get_resp = await client.get(
            f"/api/v1/orgs/{org_id}",
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "New Bakery"

    async def test_rename_rejects_empty_name(self, client, user_a):
        org_resp = await client.post(
            "/api/v1/orgs",
            json={"name": "No Empty"},
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        org_id = org_resp.json()["id"]

        response = await client.patch(
            f"/api/v1/orgs/{org_id}",
            json={"name": ""},
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        assert response.status_code == 422

    async def test_non_owner_cannot_rename(self, client, user_a, user_b):
        org_resp = await client.post(
            "/api/v1/orgs",
            json={"name": "Owner Only"},
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        org_id = org_resp.json()["id"]

        response = await client.patch(
            f"/api/v1/orgs/{org_id}",
            json={"name": "Hacked Name"},
            headers={"Authorization": f"Bearer {user_b['access_token']}"},
        )
        assert response.status_code == 403

        get_resp = await client.get(
            f"/api/v1/orgs/{org_id}",
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        assert get_resp.json()["name"] == "Owner Only"


class TestOrgDelete:
    async def test_owner_deletes_org(self, client, user_a):
        org_resp = await client.post(
            "/api/v1/orgs",
            json={"name": "To Delete"},
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        org_id = org_resp.json()["id"]

        delete_resp = await client.delete(
            f"/api/v1/orgs/{org_id}",
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        assert delete_resp.status_code == 204

        list_resp = await client.get(
            "/api/v1/orgs",
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        assert list_resp.json() == []

    async def test_non_owner_cannot_delete(self, client, user_a, user_b):
        org_resp = await client.post(
            "/api/v1/orgs",
            json={"name": "Not Yours"},
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        org_id = org_resp.json()["id"]

        delete_resp = await client.delete(
            f"/api/v1/orgs/{org_id}",
            headers={"Authorization": f"Bearer {user_b['access_token']}"},
        )
        assert delete_resp.status_code == 403

        list_resp = await client.get(
            "/api/v1/orgs",
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        assert any(o["id"] == org_id for o in list_resp.json())

    async def test_delete_org_removes_all_org_data(self, client, user_a):
        org_resp = await client.post(
            "/api/v1/orgs",
            json={"name": "Full Org"},
            headers={"Authorization": f"Bearer {user_a['access_token']}"},
        )
        org_id = org_resp.json()["id"]
        headers = {"Authorization": f"Bearer {user_a['access_token']}"}

        await client.post(
            f"/api/v1/clients?org_id={org_id}",
            json={"name": "Anna", "surname": "Nowak"},
            headers=headers,
        )
        await client.post(
            f"/api/v1/products?org_id={org_id}",
            json={"name": "Bread", "price": "5.00"},
            headers=headers,
        )

        delete_resp = await client.delete(f"/api/v1/orgs/{org_id}", headers=headers)
        assert delete_resp.status_code == 204

        list_resp = await client.get("/api/v1/orgs", headers=headers)
        assert list_resp.json() == []
