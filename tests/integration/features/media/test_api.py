import uuid

import pytest
import pytest_asyncio

# Minimal valid JPEG bytes (magic + minimal data)
JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    + b"\x00" * 512
)
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 512


@pytest.fixture(autouse=True)
def mock_s3(monkeypatch):
    async def fake_upload(file_bytes, key, content_type):
        return True

    async def fake_presigned(key, expires=300):
        return f"https://fake-s3.example.com/{key}?expires={expires}"

    async def fake_delete(key):
        return True

    import app.features.media.service as svc_module
    import app.shared.s3 as s3_module

    monkeypatch.setattr(s3_module.s3_client, "upload_file", fake_upload)
    monkeypatch.setattr(s3_module.s3_client, "get_presigned_url", fake_presigned)
    monkeypatch.setattr(s3_module.s3_client, "delete_file", fake_delete)
    # service module holds same object but patch anyway
    monkeypatch.setattr(svc_module.s3_client, "upload_file", fake_upload)
    monkeypatch.setattr(svc_module.s3_client, "get_presigned_url", fake_presigned)
    monkeypatch.setattr(svc_module.s3_client, "delete_file", fake_delete)


async def register_user_and_org(client, email_prefix: str):
    email = f"{email_prefix}_{uuid.uuid4().hex[:8]}@test.com"
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "Password123",
            "full_name": "Test User",
            "consent_to_processing": True,
        },
    )
    assert reg.status_code == 201, reg.text
    user_data = reg.json()
    org = await client.post(
        "/api/v1/orgs",
        json={"name": f"Org {email_prefix} {uuid.uuid4().hex[:4]}"},
        headers={"Authorization": f"Bearer {user_data['access_token']}"},
    )
    assert org.status_code == 201, org.text
    return user_data, org.json()


@pytest_asyncio.fixture
async def user_org(client):
    user_data, org_data = await register_user_and_org(client, "media_owner")
    return user_data, org_data


@pytest_asyncio.fixture
async def other_user_org(client):
    user_data, org_data = await register_user_and_org(client, "media_intruder")
    return user_data, org_data


async def create_product(client, user_data, org_data, name="TestProd"):
    resp = await client.post(
        "/api/v1/products",
        json={"name": name, "price": 100.0, "product_type": "good"},
        headers={"Authorization": f"Bearer {user_data['access_token']}"},
        params={"org_id": org_data["id"]},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def create_client_entity(client, user_data, org_data, name="TestClient"):
    resp = await client.post(
        "/api/v1/clients",
        json={
            "name": name,
            "surname": "Sur",
            "phone": f"+7{uuid.uuid4().int % 10000000000:010d}",
        },
        headers={"Authorization": f"Bearer {user_data['access_token']}"},
        params={"org_id": org_data["id"]},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def create_order(client, user_data, org_data):
    resp = await client.post(
        "/api/v1/orders",
        json={},
        headers={"Authorization": f"Bearer {user_data['access_token']}"},
        params={"org_id": org_data["id"]},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestMediaIDORUpload:
    async def test_upload_to_other_org_product_returns_404(
        self, client, user_org, other_user_org
    ):
        owner_user, owner_org = user_org
        intruder_user, intruder_org = other_user_org
        prod = await create_product(client, owner_user, owner_org, name="OwnerProd")
        # intruder tries to upload to owner's product using intruder's org_id
        resp = await client.post(
            f"/api/v1/media/upload/products/{prod['id']}",
            files={"file": ("photo.jpg", JPEG_BYTES, "image/jpeg")},
            headers={"Authorization": f"Bearer {intruder_user['access_token']}"},
            params={"org_id": intruder_org["id"]},
        )
        assert resp.status_code == 404, resp.text
        # owner product photos still empty
        get_resp = await client.get(
            f"/api/v1/products/{prod['id']}",
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert get_resp.status_code == 200
        assert get_resp.json()["photos"] == [] or get_resp.json().get("photos") == []

    async def test_upload_to_other_org_client_returns_404(
        self, client, user_org, other_user_org
    ):
        owner_user, owner_org = user_org
        intruder_user, intruder_org = other_user_org
        cli = await create_client_entity(client, owner_user, owner_org)
        resp = await client.post(
            f"/api/v1/media/upload/clients/{cli['id']}",
            files={"file": ("photo.jpg", JPEG_BYTES, "image/jpeg")},
            headers={"Authorization": f"Bearer {intruder_user['access_token']}"},
            params={"org_id": intruder_org["id"]},
        )
        assert resp.status_code == 404, resp.text

    async def test_upload_to_other_org_order_returns_404(
        self, client, user_org, other_user_org
    ):
        owner_user, owner_org = user_org
        intruder_user, intruder_org = other_user_org
        order = await create_order(client, owner_user, owner_org)
        resp = await client.post(
            f"/api/v1/media/upload/orders/{order['id']}",
            files={"file": ("photo.jpg", JPEG_BYTES, "image/jpeg")},
            headers={"Authorization": f"Bearer {intruder_user['access_token']}"},
            params={"org_id": intruder_org["id"]},
        )
        assert resp.status_code == 404, resp.text

    async def test_upload_unknown_entity_type_returns_422(self, client, user_org):
        user_data, org_data = user_org
        prod = await create_product(client, user_data, org_data)
        resp = await client.post(
            f"/api/v1/media/upload/unknown/{prod['id']}",
            files={"file": ("photo.jpg", JPEG_BYTES, "image/jpeg")},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert resp.status_code == 422, resp.text


class TestMediaIDORPresign:
    async def test_get_presigned_foreign_key_returns_404(
        self, client, user_org, other_user_org
    ):
        owner_user, owner_org = user_org
        intruder_user, intruder_org = other_user_org
        prod = await create_product(client, owner_user, owner_org)
        # owner uploads
        upload = await client.post(
            f"/api/v1/media/upload/products/{prod['id']}",
            files={"file": ("photo.jpg", JPEG_BYTES, "image/jpeg")},
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert upload.status_code == 200, upload.text
        key = upload.json()["key"]
        assert key.startswith(f"{owner_org['id']}/")
        # intruder tries to GET presigned for owner's key with intruder org
        resp = await client.get(
            f"/api/v1/media/{key}",
            headers={"Authorization": f"Bearer {intruder_user['access_token']}"},
            params={"org_id": intruder_org["id"]},
        )
        assert resp.status_code == 404, resp.text
        # owner can GET with own org
        resp2 = await client.get(
            f"/api/v1/media/{key}",
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert resp2.status_code == 302, resp2.text
        assert "fake-s3" in resp2.headers.get("location", "")

    async def test_garbage_path_returns_404(self, client, user_org):
        user_data, org_data = user_org
        # garbage like list/clients/uuid without prefix should be 404
        garbage = f"list/clients/{uuid.uuid4()}"
        resp = await client.get(
            f"/api/v1/media/{garbage}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert resp.status_code == 404, resp.text
        # also without org param would be 422, but with correct org prefix fails
        # try path that not start with org_id
        resp2 = await client.get(
            "/api/v1/media/some/other/path.jpg",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert resp2.status_code == 404

    async def test_get_without_org_prefix_even_own_like_fails(
        self, client, user_org, other_user_org
    ):
        owner_user, owner_org = user_org
        intruder_user, intruder_org = other_user_org
        prod = await create_product(client, owner_user, owner_org)
        upload = await client.post(
            f"/api/v1/media/upload/products/{prod['id']}",
            files={"file": ("photo.jpg", JPEG_BYTES, "image/jpeg")},
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert upload.status_code == 200
        key = upload.json()["key"]
        # intruder tries with owner's org in key but intruder's org param -> 404
        resp = await client.get(
            f"/api/v1/media/{key}",
            headers={"Authorization": f"Bearer {intruder_user['access_token']}"},
            params={"org_id": intruder_org["id"]},
        )
        assert resp.status_code == 404


class TestMediaIDORDelete:
    async def test_delete_foreign_key_returns_404(
        self, client, user_org, other_user_org
    ):
        owner_user, owner_org = user_org
        intruder_user, intruder_org = other_user_org
        prod = await create_product(client, owner_user, owner_org)
        upload = await client.post(
            f"/api/v1/media/upload/products/{prod['id']}",
            files={"file": ("photo.jpg", JPEG_BYTES, "image/jpeg")},
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert upload.status_code == 200
        key = upload.json()["key"]
        # intruder DELETE
        resp = await client.delete(
            f"/api/v1/media/{key}",
            headers={"Authorization": f"Bearer {intruder_user['access_token']}"},
            params={"org_id": intruder_org["id"]},
        )
        assert resp.status_code == 404, resp.text
        # owner still has photo
        get_prod = await client.get(
            f"/api/v1/products/{prod['id']}",
            headers={"Authorization": f"Bearer {owner_user['access_token']}"},
            params={"org_id": owner_org["id"]},
        )
        assert get_prod.status_code == 200
        assert key in (get_prod.json().get("photos") or [])

    async def test_delete_garbage_path_returns_404(self, client, user_org):
        user_data, org_data = user_org
        garbage = f"list/clients/{uuid.uuid4()}"
        resp = await client.delete(
            f"/api/v1/media/{garbage}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert resp.status_code == 404


class TestMediaList:
    async def _upload(
        self, client, user_data, org_data, entity_type: str, entity_id: str
    ) -> str:
        upload = await client.post(
            f"/api/v1/media/upload/{entity_type}/{entity_id}",
            files={"file": ("photo.jpg", JPEG_BYTES, "image/jpeg")},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert upload.status_code == 200, upload.text
        return upload.json()["key"]

    async def test_list_own_product_photos_returns_keys(self, client, user_org):
        user_data, org_data = user_org
        prod = await create_product(client, user_data, org_data)
        key1 = await self._upload(client, user_data, org_data, "products", prod["id"])
        key2 = await self._upload(client, user_data, org_data, "products", prod["id"])
        resp = await client.get(
            f"/api/v1/media/list/products/{prod['id']}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert resp.status_code == 200, resp.text
        assert sorted(item["key"] for item in resp.json()) == sorted([key1, key2])
        # only keys, no extra fields
        assert set(resp.json()[0].keys()) == {"key"}

    async def test_list_own_client_and_order(self, client, user_org):
        user_data, org_data = user_org
        cli = await create_client_entity(client, user_data, org_data)
        order = await create_order(client, user_data, org_data)
        cli_key = await self._upload(client, user_data, org_data, "clients", cli["id"])
        order_key = await self._upload(
            client, user_data, org_data, "orders", order["id"]
        )

        cli_resp = await client.get(
            f"/api/v1/media/list/clients/{cli['id']}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert cli_resp.status_code == 200
        assert [item["key"] for item in cli_resp.json()] == [cli_key]

        order_resp = await client.get(
            f"/api/v1/media/list/orders/{order['id']}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert order_resp.status_code == 200
        assert [item["key"] for item in order_resp.json()] == [order_key]

    async def test_list_empty_when_no_photos(self, client, user_org):
        user_data, org_data = user_org
        prod = await create_product(client, user_data, org_data)
        resp = await client.get(
            f"/api/v1/media/list/products/{prod['id']}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_foreign_entity_404(self, client, user_org, other_user_org):
        owner_user, owner_org = user_org
        intruder_user, intruder_org = other_user_org
        prod = await create_product(client, owner_user, owner_org)
        await self._upload(client, owner_user, owner_org, "products", prod["id"])
        resp = await client.get(
            f"/api/v1/media/list/products/{prod['id']}",
            headers={"Authorization": f"Bearer {intruder_user['access_token']}"},
            params={"org_id": intruder_org["id"]},
        )
        assert resp.status_code == 404, resp.text

    async def test_list_missing_entity_returns_404(self, client, user_org):
        user_data, org_data = user_org
        resp = await client.get(
            f"/api/v1/media/list/products/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert resp.status_code == 404

    async def test_list_unknown_entity_type_returns_404(self, client, user_org):
        user_data, org_data = user_org
        prod = await create_product(client, user_data, org_data)
        resp = await client.get(
            f"/api/v1/media/list/unknown/{prod['id']}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert resp.status_code == 404


class TestMediaOwnSuccess:
    async def test_upload_get_delete_product_ok(self, client, user_org):
        user_data, org_data = user_org
        prod = await create_product(client, user_data, org_data, name="ProdForMedia")
        # upload
        upload = await client.post(
            f"/api/v1/media/upload/products/{prod['id']}",
            files={"file": ("photo.jpg", JPEG_BYTES, "image/jpeg")},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert upload.status_code == 200, upload.text
        key = upload.json()["key"]
        assert key.startswith(f"{org_data['id']}/products/{prod['id']}/")
        # list via entity photos
        get_prod = await client.get(
            f"/api/v1/products/{prod['id']}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert get_prod.status_code == 200
        assert key in get_prod.json()["photos"]
        # get presigned
        get_media = await client.get(
            f"/api/v1/media/{key}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert get_media.status_code == 302
        assert key in get_media.headers.get("location", "")
        # delete
        del_resp = await client.delete(
            f"/api/v1/media/{key}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "ok"
        # verify removed from entity
        get_prod2 = await client.get(
            f"/api/v1/products/{prod['id']}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert get_prod2.status_code == 200
        assert key not in (get_prod2.json().get("photos") or [])

    async def test_upload_list_delete_client_ok(self, client, user_org):
        user_data, org_data = user_org
        cli = await create_client_entity(client, user_data, org_data)
        upload = await client.post(
            f"/api/v1/media/upload/clients/{cli['id']}",
            files={"file": ("photo.jpg", JPEG_BYTES, "image/jpeg")},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert upload.status_code == 200, upload.text
        key = upload.json()["key"]
        assert key.startswith(f"{org_data['id']}/clients/{cli['id']}/")
        # verify client photos
        get_cli = await client.get(
            f"/api/v1/clients/{cli['id']}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert get_cli.status_code == 200
        assert key in get_cli.json()["photos"]
        # get presigned
        get_media = await client.get(
            f"/api/v1/media/{key}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert get_media.status_code == 302
        # delete
        del_resp = await client.delete(
            f"/api/v1/media/{key}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert del_resp.status_code == 200
        # verify gone
        get_cli2 = await client.get(
            f"/api/v1/clients/{cli['id']}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert key not in (get_cli2.json().get("photos") or [])

    async def test_upload_list_delete_order_ok(self, client, user_org):
        user_data, org_data = user_org
        order = await create_order(client, user_data, org_data)
        upload = await client.post(
            f"/api/v1/media/upload/orders/{order['id']}",
            files={"file": ("photo.jpg", JPEG_BYTES, "image/jpeg")},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert upload.status_code == 200, upload.text
        key = upload.json()["key"]
        assert key.startswith(f"{org_data['id']}/orders/{order['id']}/")
        # verify order photos via get order
        get_order = await client.get(
            f"/api/v1/orders/{order['id']}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert get_order.status_code == 200
        assert key in get_order.json()["photos"]
        # get presigned
        get_media = await client.get(
            f"/api/v1/media/{key}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert get_media.status_code == 302
        # delete
        del_resp = await client.delete(
            f"/api/v1/media/{key}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert del_resp.status_code == 200
        get_order2 = await client.get(
            f"/api/v1/orders/{order['id']}",
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert key not in (get_order2.json().get("photos") or [])

    async def test_upload_client_reuses_org_prefix(self, client, user_org):
        user_data, org_data = user_org
        cli = await create_client_entity(client, user_data, org_data)
        upload = await client.post(
            f"/api/v1/media/upload/clients/{cli['id']}",
            files={"file": ("photo.png", PNG_BYTES, "image/png")},
            headers={"Authorization": f"Bearer {user_data['access_token']}"},
            params={"org_id": org_data["id"]},
        )
        assert upload.status_code == 200
        key = upload.json()["key"]
        assert key.startswith(f"{org_data['id']}/clients/")
        assert key.endswith(".png")
