import csv
import io
from typing import Any

MAX_EXPORT_ROWS = 10_000
_BOM = "\ufeff"


def rows_to_csv(rows: list[dict[str, Any]], headers: list[str]) -> str:
    """Serialize rows to CSV with UTF-8 BOM (Excel-friendly)."""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)

    return _BOM + output.getvalue()


def add_custom_columns(
    row: dict[str, Any], custom_fields: dict | None
) -> dict[str, Any]:
    """Flatten JSONB custom/local fields into `cf_<key>` columns (sorted)."""
    fields = custom_fields or {}

    for key in sorted(fields):
        row[f"cf_{key}"] = fields[key]

    return row


def ensure_export_limit(rows: list) -> None:
    if len(rows) > MAX_EXPORT_ROWS:
        raise ValueError(f"Export exceeds maximum of {MAX_EXPORT_ROWS} rows")
