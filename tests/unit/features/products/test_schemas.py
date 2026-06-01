"""Regression tests: Product name length validation.

Bug: creating a product with a >255 char name caused HTTP 500
(Postgres value too long for String(255)) instead of a 422.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.features.products.schemas import ProductCreate, ProductUpdate


class TestProductCreateNameLength:
    async def test_name_at_max_length_accepted(self):
        product = ProductCreate(name="x" * 255, price=Decimal("10"))
        assert len(product.name) == 255

    async def test_name_over_255_rejected(self):
        with pytest.raises(ValidationError) as exc:
            ProductCreate(name="x" * 256)
        errors = exc.value.errors()
        assert errors[0]["type"] == "string_too_long"
        assert errors[0]["loc"] == ("name",)

    async def test_short_name_accepted(self):
        product = ProductCreate(name="Baguette")
        assert product.name == "Baguette"


class TestProductUpdateNameLength:
    async def test_update_name_over_255_rejected(self):
        with pytest.raises(ValidationError) as exc:
            ProductUpdate(name="x" * 256)
        errors = exc.value.errors()
        assert errors[0]["type"] == "string_too_long"
        assert errors[0]["loc"] == ("name",)

    async def test_update_name_at_max_length_accepted(self):
        product = ProductUpdate(name="x" * 255)
        assert product.name is not None
        assert len(product.name) == 255

    async def test_update_name_omitted_accepted(self):
        product = ProductUpdate(price=Decimal("5"))
        assert product.name is None
