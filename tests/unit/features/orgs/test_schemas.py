"""Regression tests: Org settings currency ISO-4217 validation.

Bug: PUT /api/v1/orgs/{id}/settings accepted any string as currency.
"""

import pytest
from pydantic import ValidationError

from app.features.orgs.schemas import OrgSettingsUpdate


class TestOrgSettingsCurrency:
    async def test_valid_currencies_accepted(self):
        for code in ("RUB", "PLN", "USD", "EUR", "BYN", "KZT", "UAH"):
            settings = OrgSettingsUpdate(currency=code)
            assert settings.currency == code

    async def test_default_currency_is_pln(self):
        settings = OrgSettingsUpdate()
        assert settings.currency == "PLN"

    async def test_invalid_currency_rejected(self):
        with pytest.raises(ValidationError) as exc:
            OrgSettingsUpdate.model_validate({"currency": "XYZ"})
        errors = exc.value.errors()
        assert errors[0]["type"] == "value_error"
        assert errors[0]["loc"] == ("currency",)

    async def test_lowercase_currency_rejected(self):
        with pytest.raises(ValidationError):
            OrgSettingsUpdate.model_validate({"currency": "usd"})
