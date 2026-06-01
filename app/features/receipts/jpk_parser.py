"""
 JPK Parser - parsing electronic receipts in JPK_KASA format.

Parses the JPK fiscal core (Layer 2) with Polish keys:
naglowek, podmiot1, paragon, pozycja, towar. A JWT-wrapped payload
(in the 'data' field) is also accepted and decoded as Layer 2.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.features.receipts.schemas import ReceiptItemCreate


@dataclass
class JpkParseResult:
    """Result of parsing a JPK receipt."""

    source: str = ""
    tin: str = ""  # Seller's NIP
    seller_name: str = ""  # Seller name
    receipt_date: str = ""  # Receipt date (ISO)
    total: Decimal = Decimal(0)  # Total amount
    items: list[ReceiptItemCreate] = field(default_factory=list)
    raw_data: dict | None = None  # Original JSON
    errors: list[str] = field(default_factory=list)
    format_detected: str = ""  # layer1 / layer2 / unknown

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


def _parse_groszy(value: Any) -> Decimal:
    """Convert groszy (whole numbers) to zloty (Decimal).

    In JPK, all prices are whole numbers (groszy). Divide by 100.
    """

    try:
        return Decimal(str(value)) / Decimal("100")
    except (InvalidOperation, ValueError):
        return Decimal(0)


def _parse_quantity(value: Any) -> Decimal:
    """Parse a quantity, treating a comma as the decimal separator.

    In JPK, the quantity/ilosc field may contain '0,476' instead of '0.476'.
    """

    if isinstance(value, str):
        value = value.replace(",", ".")

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal(1)


# Complex branch-heavy parser; refactoring is out of scope for this task
def _parse_layer2(data: dict) -> JpkParseResult:  # noqa: C901
    """Parse Layer 2: the JPK fiscal core (Polish keys).

    Format:
    {
      "document": {
        "naglowek": { "wersja": "...", "dataJPK": "..." },
        "podmiot1": { "NIP": "...", "nazwaPod": "..." },
        "paragon": {
          "JPKID": 123,
          "pozycja": [
            { "towar": { "nazwa": "...", "brutto": 1234, "rabat": { "wart": 100 } } }
          ]
        }
      }
    }
    """
    result = JpkParseResult(format_detected="layer2", raw_data=data)

    # Accept both English 'document' and Polish 'dokument' keys
    doc = data.get("document") or data.get("dokument") or {}

    if not doc:
        result.errors.append("document key is missing")

        return result

    podmiot = doc.get("podmiot1", {})
    result.tin = str(podmiot.get("NIP", ""))
    result.seller_name = str(podmiot.get("nazwaPod", ""))
    result.source = "jpk"

    naglowek = doc.get("naglowek", {})
    raw_date = naglowek.get("dataJPK", "")

    if raw_date:
        try:
            dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            result.receipt_date = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            result.receipt_date = datetime.now().strftime("%Y-%m-%d %H:%M")
    else:
        result.receipt_date = datetime.now().strftime("%Y-%m-%d %H:%M")

    paragon = doc.get("paragon", {})
    pozycje = paragon.get("pozycja", [])

    if not isinstance(pozycje, list):
        result.errors.append("paragon.pozycja must be an array")

        return result

    total = Decimal(0)

    for pozycja in pozycje:
        towar = pozycja.get("towar", {})

        if not towar:
            continue

        name = str(towar.get("nazwa", ""))

        # Quantity: prefer towar.ilosc, fall back to pozycja.ilosc
        qty = _parse_quantity(towar.get("ilosc", None) or pozycja.get("ilosc", 1))

        # Unit price: prefer 'cena' (unit price in groszy). If missing, derive
        # from 'brutto'.
        unit_price = None

        if towar.get("cena") is not None:
            unit_price = _parse_groszy(towar.get("cena"))
        else:
            brutto = _parse_groszy(towar.get("brutto", 0))

            try:
                unit_price = (brutto / qty) if qty != 0 else brutto
            except Exception:
                unit_price = brutto

        # Discounts: if present, assume 'wart' is total discount for the position
        rabat = towar.get("rabat", {})
        discount_total = (
            _parse_groszy(rabat.get("wart", 0))
            if isinstance(rabat, dict)
            else Decimal(0)
        )
        discount_per_unit = (discount_total / qty) if qty != 0 else discount_total

        final_unit_price = unit_price - discount_per_unit

        if final_unit_price < 0:
            final_unit_price = Decimal(0)

        # Round to 2 decimal places for display/storage
        final_unit_price = final_unit_price.quantize(Decimal("0.01"))

        line_total = (final_unit_price * qty).quantize(Decimal("0.01"))
        total += line_total

        result.items.append(
            ReceiptItemCreate(
                product_id=None,
                name=name,
                price=final_unit_price,
                qty=qty,
            )
        )

    # Total rounded to 2 decimals
    result.total = total.quantize(Decimal("0.01"))

    if not result.items:
        result.errors.append("no items found in paragon.pozycja")

    return result


# Complex branch-heavy parser; refactoring is out of scope for this task
def parse_jpk(json_data: dict) -> JpkParseResult:
    """Parse a JPK receipt (Layer 2 fiscal core).

    - If a JWT token is present in the 'data' field, its payload is decoded
      and parsed as Layer 2 (signature is not verified).
    - A top-level 'document' key -> Layer 2.
    - Bare 'paragon'/'naglowek' keys -> wrapped as Layer 2.
    """

    if not isinstance(json_data, dict):
        result = JpkParseResult(format_detected="unknown")
        result.errors.append("input must be a JSON object")

        return result

    # A JWT token in 'data' -> decode the payload (segment 2) as Layer 2
    data_field = json_data.get("data")

    if data_field and isinstance(data_field, str):
        import base64
        import json as stdjson

        parts = data_field.split(".")

        if len(parts) == 3:
            try:
                payload_b64 = parts[1]
                padding = 4 - len(payload_b64) % 4

                if padding != 4:
                    payload_b64 += "=" * padding

                decoded = base64.urlsafe_b64decode(payload_b64)
                inner_data = stdjson.loads(decoded)

                return _parse_layer2(inner_data)
            except Exception:  # noqa: S110
                pass

    # Layer 2: document
    if "document" in json_data:
        return _parse_layer2(json_data)

    # If data is already a parsed payload (passed directly)
    if "paragon" in json_data or "naglowek" in json_data:
        return _parse_layer2({"document": json_data})

    result = JpkParseResult(format_detected="unknown")
    result.errors.append(
        "unrecognized JPK format. Expected Layer 2 (document/naglowek/paragon)"
    )

    return result
