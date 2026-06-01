"""Unit tests for JPK parser."""

from decimal import Decimal

from app.features.receipts.jpk_parser import (
    _parse_groszy,
    parse_jpk,
)


class TestParseGroszy:
    def test_groszy_to_decimal(self):
        assert _parse_groszy(1234) == Decimal("12.34")
        assert _parse_groszy(0) == Decimal("0")
        assert _parse_groszy(100) == Decimal("1.00")

    def test_groszy_with_string(self):
        assert _parse_groszy("500") == Decimal("5.00")
        assert _parse_groszy("0") == Decimal("0")

    def test_groszy_invalid_returns_zero(self):
        assert _parse_groszy(None) == Decimal("0")
        assert _parse_groszy("abc") == Decimal("0")


class TestParseLayer2:
    """Layer 2: JPK fiscal core with Polish keys."""

    def test_basic_receipt(self):
        data = {
            "document": {
                "naglowek": {"wersja": "1.0", "dataJPK": "2025-06-07T14:30:00"},
                "podmiot1": {"NIP": "9876543210", "nazwaPod": "Biedronka Sp. z o.o."},
                "paragon": {
                    "JPKID": 12345,
                    "pozycja": [
                        {"towar": {"nazwa": "Chleb", "brutto": 500, "ilosc": 1}},
                        {"towar": {"nazwa": "Mleko", "brutto": 320, "ilosc": 2}},
                    ],
                },
            }
        }
        result = parse_jpk(data)
        assert result.format_detected == "layer2"
        assert result.tin == "9876543210"
        assert result.seller_name == "Biedronka Sp. z o.o."
        assert result.receipt_date.startswith("2025-06-07")
        assert len(result.items) == 2
        assert not result.has_errors

    def test_with_discount(self):
        data = {
            "document": {
                "naglowek": {"wersja": "1.0"},
                "podmiot1": {"NIP": "123"},
                "paragon": {
                    "pozycja": [
                        {
                            "towar": {
                                "nazwa": "Maslo",
                                "brutto": 800,
                                "rabat": {"wart": 150},
                                "ilosc": 1,
                            }
                        },
                    ],
                },
            }
        }
        result = parse_jpk(data)
        assert result.items[0].price == Decimal("6.50")

    def test_no_document_returns_error(self):
        result = parse_jpk({})
        assert result.has_errors

    def test_empty_items_returns_error(self):
        data = {
            "document": {
                "podmiot1": {"NIP": "123"},
                "paragon": {"pozycja": []},
            }
        }
        result = parse_jpk(data)
        assert result.has_errors


class TestJwtLayer2:
    """Layer 1 with a JWT token in the data field containing Layer 2."""

    def test_jwt_payload_decoded(self):
        import base64
        import json

        inner = {
            "document": {
                "naglowek": {"wersja": "1.0"},
                "podmiot1": {"NIP": "1112223334"},
                "paragon": {
                    "pozycja": [{"towar": {"nazwa": "Jogurt", "brutto": 250}}],
                },
            }
        }
        payload_b64 = (
            base64.urlsafe_b64encode(json.dumps(inner).encode()).decode().rstrip("=")
        )
        fake_jwt = f"header.{payload_b64}.signature"

        data = {
            "protoVersion": "1.0",
            "data": fake_jwt,
            "header": {"tin": "1112223334"},
            "body": [],
        }
        result = parse_jpk(data)
        # Must parse Layer 2 from the JWT
        assert result.tin == "1112223334"
        assert len(result.items) == 1
        assert result.items[0].name == "Jogurt"


class TestUnknownFormat:
    def test_non_dict_input(self):
        result = parse_jpk("not a dict")  # type: ignore
        assert result.has_errors

    def test_unknown_structure(self):
        result = parse_jpk({"unknown": "data"})
        assert result.has_errors
        assert "unrecognized" in result.errors[0]
