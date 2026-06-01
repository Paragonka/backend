"""Web form helpers shared between feature web_routers (HTMX forms).

These were previously duplicated inline in clients/products/orders/receipts
web_routers. Keeping them here lets routers stay thin (pure transport glue)
while the parsing rules live in one place.
"""

from typing import Any


def extract_local_fields(form: Any) -> dict[str, str]:
    """Collapse parallel lf_key / lf_value form lists into a dict."""
    keys = form.getlist("lf_key")
    values = form.getlist("lf_value")
    result = {}

    for k, v in zip(keys, values, strict=False):
        if k.strip():
            result[k.strip()] = v.strip()

    return result


def normalize_datetime(raw: str) -> str:
    """Normalize an HTML datetime-local value (with 'T') to a space-separated one."""

    return raw.replace("T", " ") if "T" in raw else raw


def empty_to_none(value: str | None) -> str | None:
    """Convert an empty form value to None (empty optional FK selects)."""
    value = str(value or "")

    return value if value != "" else None


def parse_eav_filters(query_params: Any) -> dict[str, str]:
    """Extract eav[code]=value filters from request.query_params."""
    filters = {}

    for key, value in query_params.items():
        if key.startswith("eav[") and key.endswith("]") and value:
            code = key[4:-1]
            filters[code] = value

    return filters
