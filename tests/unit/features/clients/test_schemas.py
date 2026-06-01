"""Regression tests for client schemas.

- ClientCreate/ClientUpdate name/surname/phone length validation
  (long values caused HTTP 500 instead of 422).
- ClientResponse exposes `photos` so the frontend can render client photos.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.features.clients.schemas import ClientCreate, ClientResponse, ClientUpdate


class TestClientCreateLengths:
    async def test_surname_over_255_rejected(self):
        with pytest.raises(ValidationError) as exc:
            ClientCreate(name="Иван", surname="x" * 256)
        errors = exc.value.errors()
        assert errors[0]["type"] == "string_too_long"
        assert errors[0]["loc"] == ("surname",)

    async def test_phone_over_20_rejected(self):
        with pytest.raises(ValidationError) as exc:
            ClientCreate(name="Иван", phone="1" * 21)
        errors = exc.value.errors()
        assert errors[0]["type"] == "string_too_long"
        assert errors[0]["loc"] == ("phone",)

    async def test_surname_at_max_length_accepted(self):
        client = ClientCreate(name="Иван", surname="x" * 255)
        assert len(client.surname) == 255


class TestClientUpdateLengths:
    async def test_surname_over_255_rejected(self):
        with pytest.raises(ValidationError) as exc:
            ClientUpdate(surname="x" * 256)
        errors = exc.value.errors()
        assert errors[0]["type"] == "string_too_long"
        assert errors[0]["loc"] == ("surname",)

    async def test_phone_over_20_rejected(self):
        with pytest.raises(ValidationError) as exc:
            ClientUpdate(phone="1" * 21)
        errors = exc.value.errors()
        assert errors[0]["type"] == "string_too_long"
        assert errors[0]["loc"] == ("phone",)


class TestClientResponsePhotos:
    async def test_photos_default_to_empty_list(self):
        client = ClientResponse(
            id=uuid4(),
            org_id=uuid4(),
            name="Иван",
            surname="Иванов",
            phone="+7999",
            notes="",
        )
        assert client.photos == []

    async def test_photos_preserved_from_response(self):
        keys = ["org/clients/id/photo1.jpg", "org/clients/id/photo2.png"]
        client = ClientResponse(
            id=uuid4(),
            org_id=uuid4(),
            name="Иван",
            surname="Иванов",
            phone="+7999",
            notes="",
            photos=keys,
        )
        assert client.photos == keys
