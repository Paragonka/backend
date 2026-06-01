import csv
import io
from typing import Any

CLIENT_CSV_COLUMNS = {"name", "surname", "phone", "notes", "custom_fields"}
PRODUCT_CSV_COLUMNS = {
    "name",
    "category",
    "unit",
    "product_type",
    "price",
    "cost_price",
    "stock_qty",
    "track_inventory",
    "is_sellable",
    "is_active",
    "custom_fields",
}


def parse_bool(value: str | None) -> bool:
    """Parse a CSV string value into a bool.

    Treats 'true'/'1'/'yes'/'y'/'t' (case-insensitive, whitespace-trimmed)
    as True; 'false'/'0'/'no'/'n'/''/None as False. Avoids the Python
    pitfall where bool("False") == True.
    """
    if value is None:
        return False

    normalized = str(value).strip().lower()

    return normalized in ("true", "1", "yes", "y", "t")


class CsvImportResult:
    def __init__(self):
        self.created: int = 0
        self.updated: int = 0
        self.errors: list[dict[str, Any]] = []

    @property
    def imported(self) -> int:
        return self.created + self.updated

    def add_error(self, row: int, error: str) -> None:
        self.errors.append({"row": row, "error": error})


def validate_csv_columns(
    headers: list[str], allowed: set[str], entity_name: str
) -> list[str]:
    """Validate CSV headers against allowed columns. Returns list of errors."""
    errors = []
    header_set = {h.strip().lower() for h in headers}
    unknown = header_set - allowed

    if unknown:
        errors.append(
            f"Unknown columns: {sorted(unknown)}. "
            f"Allowed columns for {entity_name}: {sorted(allowed)}"
        )

    return errors


def parse_csv(
    content: bytes,
) -> tuple[list[str], list[dict[str, str]]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        raise ValueError("CSV file has no headers")

    rows: list[dict[str, str]] = []

    for _i, row in enumerate(reader, start=2):
        rows.append({k.strip(): v.strip() for k, v in row.items()})

    return list(reader.fieldnames), rows
