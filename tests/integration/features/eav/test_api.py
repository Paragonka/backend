import pytest_asyncio


@pytest_asyncio.fixture
async def user_org(client):
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "eavtest@test.com",
            "password": "Password123",
            "full_name": "Test User",
            "consent_to_processing": True,
        },
    )
    user_data = reg.json()
    org = await client.post(
        "/api/v1/orgs",
        json={"name": "EAV Org"},
        headers={"Authorization": f"Bearer {user_data['access_token']}"},
    )
    org_data = org.json()
    return user_data, org_data


class TestEavAttributeAPI:
    async def test_create_attribute(self, client, user_org):
        user_data, org_data = user_org
        response = await client.post(
            "/api/v1/eav/attributes",
            json={
                "entity_code": "product",
                "code": "color",
                "name": "Цвет",
                "field_type": "string",
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "color"
        assert data["name"] == "Цвет"
        assert data["entity_code"] == "product"
        assert data["field_type"] == "string"
        assert data["is_required"] is False

    async def test_list_attributes_by_entity_code(self, client, user_org):
        user_data, org_data = user_org
        await client.post(
            "/api/v1/eav/attributes",
            json={"entity_code": "product", "code": "color", "name": "Цвет"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        await client.post(
            "/api/v1/eav/attributes",
            json={"entity_code": "product", "code": "weight", "name": "Вес"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )

        response = await client.get(
            "/api/v1/eav/attributes",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "entity_code": "product"},
        )
        assert response.status_code == 200
        attrs = response.json()
        assert len(attrs) == 2
        codes = {a["code"] for a in attrs}
        assert codes == {"color", "weight"}

    async def test_attributes_scoped_to_org(self, client, user_org):
        user_data, org_data = user_org
        await client.post(
            "/api/v1/eav/attributes",
            json={"entity_code": "product", "code": "color", "name": "Цвет"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        other_org = await client.post(
            "/api/v1/orgs",
            json={"name": "Other EAV Org"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
        )
        other_org_data = other_org.json()
        response = await client.get(
            "/api/v1/eav/attributes",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": other_org_data["id"], "entity_code": "product"},
        )
        assert response.status_code == 200
        assert response.json() == []

    async def test_delete_attribute_keeps_others(self, client, user_org):
        user_data, org_data = user_org
        a1 = await client.post(
            "/api/v1/eav/attributes",
            json={"entity_code": "product", "code": "color", "name": "Цвет"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        await client.post(
            "/api/v1/eav/attributes",
            json={"entity_code": "product", "code": "weight", "name": "Вес"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        a1_id = a1.json()["id"]

        response = await client.delete(
            f"/api/v1/eav/attributes/{a1_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 204

        remaining = await client.get(
            "/api/v1/eav/attributes",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "entity_code": "product"},
        )
        attrs = remaining.json()
        assert len(attrs) == 1
        assert attrs[0]["code"] == "weight"

    async def test_unauthorized_access(self, client):
        response = await client.get(
            "/api/v1/eav/attributes",
            params={
                "org_id": "00000000-0000-0000-0000-000000000000",
                "entity_code": "product",
            },
        )
        assert response.status_code == 401

    async def test_delete_nonexistent_attribute_returns_404(self, client, user_org):
        user_data, org_data = user_org
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.delete(
            f"/api/v1/eav/attributes/{fake_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 404

    async def test_delete_attribute_invalid_uuid_returns_422(self, client, user_org):
        user_data, org_data = user_org
        response = await client.delete(
            "/api/v1/eav/attributes/zzz",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 422

    async def test_delete_attribute_other_org_returns_403(self, client, user_org):
        user_data, org_data = user_org
        await client.post(
            "/api/v1/eav/attributes",
            json={"entity_code": "product", "code": "secret", "name": "Секрет"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        other_org = await client.post(
            "/api/v1/orgs",
            json={"name": "Other EAV Org 2"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
        )
        other_org_data = other_org.json()

        # attribute belongs to org_data, deleting with other_org → 404
        # (cross-tenant resources are concealed as not found)
        listing = await client.get(
            "/api/v1/eav/attributes",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"], "entity_code": "product"},
        )
        attr_id = listing.json()[0]["id"]
        response = await client.delete(
            f"/api/v1/eav/attributes/{attr_id}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": other_org_data["id"]},
        )
        assert response.status_code == 404

    async def test_create_duplicate_code_returns_409(self, client, user_org):
        user_data, org_data = user_org
        headers = {"Authorization": f"Bearer {user_data['access_token']}"}
        params = {"org_id": org_data["id"]}
        payload = {
            "entity_code": "product",
            "code": "color",
            "name": "Цвет",
        }
        first = await client.post(
            "/api/v1/eav/attributes", json=payload, headers=headers, params=params
        )
        assert first.status_code == 201
        second = await client.post(
            "/api/v1/eav/attributes", json=payload, headers=headers, params=params
        )
        assert second.status_code == 409


class TestEavPatchAttribute:
    async def _create_attr(self, client, user_org, **overrides):
        user_data, org_data = user_org
        payload = {
            "entity_code": "client",
            "code": "instagram",
            "name": "Instagram",
            "field_type": "string",
        }
        payload.update(overrides)
        response = await client.post(
            "/api/v1/eav/attributes",
            json=payload,
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 201
        return response.json()

    async def test_patch_updates_name_and_is_required(self, client, user_org):
        attr = await self._create_attr(client, user_org)
        user_data, org_data = user_org
        response = await client.patch(
            f"/api/v1/eav/attributes/{attr['id']}",
            json={"name": "Инстаграм", "is_required": True},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Инстаграм"
        assert data["is_required"] is True
        assert data["code"] == "instagram"

    async def test_patch_code_and_entity_code_immutable_returns_422(
        self, client, user_org
    ):
        attr = await self._create_attr(client, user_org)
        user_data, org_data = user_org
        for immutable in ("code", "entity_code"):
            response = await client.patch(
                f"/api/v1/eav/attributes/{attr['id']}",
                json={immutable: "hacked"},
                headers={"Authorization": f"Bearer {user_data['access_token']}"},
                params={"org_id": org_data["id"]},
            )
            assert response.status_code == 422

    async def test_patch_nonexistent_attribute_returns_404(self, client, user_org):
        user_data, org_data = user_org
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await client.patch(
            f"/api/v1/eav/attributes/{fake_id}",
            json={"name": "New Name"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 404

    async def test_patch_other_org_attribute_returns_404(self, client, user_org):
        attr = await self._create_attr(client, user_org)
        user_data, _ = user_org
        other_org = await client.post(
            "/api/v1/orgs",
            json={"name": "Other Patch Org"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
        )
        other_org_data = other_org.json()
        response = await client.patch(
            f"/api/v1/eav/attributes/{attr['id']}",
            json={"name": "Hijack"},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": other_org_data["id"]},
        )
        assert response.status_code == 404

    async def test_patch_field_type_change_allowed_invalid_write_rejected(
        self, client, user_org
    ):
        attr = await self._create_attr(client, user_org)
        user_data, org_data = user_org
        headers = {"Authorization": f"Bearer {user_data['access_token']}"}
        params = {"org_id": org_data["id"]}

        created = await client.post(
            "/api/v1/clients",
            json={
                "name": "Anna",
                "phone": "+70001112233",
                "custom_fields": {"instagram": "@anna"},
            },
            headers=headers,
            params=params,
        )
        assert created.status_code == 201

        patched = await client.patch(
            f"/api/v1/eav/attributes/{attr['id']}",
            json={"field_type": "boolean"},
            headers=headers,
            params=params,
        )
        assert patched.status_code == 200
        assert patched.json()["field_type"] == "boolean"

        invalid_write = await client.post(
            "/api/v1/clients",
            json={
                "name": "Boris",
                "phone": "+70004445566",
                "custom_fields": {"instagram": "not-a-bool"},
            },
            headers=headers,
            params=params,
        )
        assert invalid_write.status_code == 422


class TestEavDeleteCleansCustomFields:
    async def test_delete_attribute_cleans_client_custom_fields(self, client, user_org):
        user_data, org_data = user_org
        headers = {"Authorization": f"Bearer {user_data['access_token']}"}
        params = {"org_id": org_data["id"]}
        attr = await client.post(
            "/api/v1/eav/attributes",
            json={
                "entity_code": "client",
                "code": "birthday",
                "name": "День рождения",
                "field_type": "date",
            },
            headers=headers,
            params=params,
        )
        attr_id = attr.json()["id"]
        created = await client.post(
            "/api/v1/clients",
            json={
                "name": "Maria",
                "phone": "+70009998877",
                "custom_fields": {"birthday": "2020-01-01"},
            },
            headers=headers,
            params=params,
        )
        assert created.status_code == 201
        client_id = created.json()["id"]

        deleted = await client.delete(
            f"/api/v1/eav/attributes/{attr_id}", headers=headers, params=params
        )
        assert deleted.status_code == 204

        fetched = await client.get(
            f"/api/v1/clients/{client_id}", headers=headers, params=params
        )
        assert fetched.status_code == 200
        assert fetched.json()["custom_fields"] == {}

    async def test_delete_attribute_cleans_product_custom_fields(
        self, client, user_org
    ):
        user_data, org_data = user_org
        headers = {"Authorization": f"Bearer {user_data['access_token']}"}
        params = {"org_id": org_data["id"]}
        attr = await client.post(
            "/api/v1/eav/attributes",
            json={
                "entity_code": "product",
                "code": "origin",
                "name": "Страна",
            },
            headers=headers,
            params=params,
        )
        attr_id = attr.json()["id"]
        created = await client.post(
            "/api/v1/products",
            json={"name": "Croissant", "unit": "шт", "custom_fields": {"origin": "FR"}},
            headers=headers,
            params=params,
        )
        assert created.status_code == 201
        product_id = created.json()["id"]

        deleted = await client.delete(
            f"/api/v1/eav/attributes/{attr_id}", headers=headers, params=params
        )
        assert deleted.status_code == 204

        fetched = await client.get(
            f"/api/v1/products/{product_id}", headers=headers, params=params
        )
        assert fetched.status_code == 200
        assert fetched.json()["custom_fields"] == {}


class TestEavValidationStrict:
    async def _create_date_attr(self, client, user_org):
        user_data, org_data = user_org
        response = await client.post(
            "/api/v1/eav/attributes",
            json={
                "entity_code": "client",
                "code": "birthday",
                "name": "День рождения",
                "field_type": "date",
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 201

    async def test_date_9999_99_99_rejected(self, client, user_org):
        await self._create_date_attr(client, user_org)
        user_data, org_data = user_org
        response = await client.post(
            "/api/v1/clients",
            json={
                "name": "Anna",
                "phone": "+70001112233",
                "custom_fields": {"birthday": "9999-99-99"},
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 422

    async def test_valid_date_accepted(self, client, user_org):
        await self._create_date_attr(client, user_org)
        user_data, org_data = user_org
        response = await client.post(
            "/api/v1/clients",
            json={
                "name": "Anna",
                "phone": "+70001112233",
                "custom_fields": {"birthday": "2026-08-24"},
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 201
        assert response.json()["custom_fields"]["birthday"] == "2026-08-24"

    async def test_unknown_custom_field_code_rejected(self, client, user_org):
        user_data, org_data = user_org
        response = await client.post(
            "/api/v1/clients",
            json={
                "name": "Ghost",
                "phone": "+70005556677",
                "custom_fields": {"not_defined": "x"},
            },
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert response.status_code == 422
        assert "not_defined" in response.json()["detail"]

    async def test_entity_code_order_ok_banana_422(self, client, user_org):
        user_data, org_data = user_org
        headers = {"Authorization": f"Bearer {user_data['access_token']}"}
        params = {"org_id": org_data["id"]}
        ok = await client.post(
            "/api/v1/eav/attributes",
            json={"entity_code": "order", "code": "source", "name": "Источник"},
            headers=headers,
            params=params,
        )
        assert ok.status_code == 201
        bad = await client.post(
            "/api/v1/eav/attributes",
            json={"entity_code": "banana", "code": "weird", "name": "Weird"},
            headers=headers,
            params=params,
        )
        assert bad.status_code == 422
