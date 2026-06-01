import base64
import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import InstrumentedAttribute


async def count_query(session: Any, base_query: Select) -> int:
    """Total count of rows matching base_query (filters, before sort/pagination)."""
    count_stmt = select(func.count()).select_from(base_query.subquery())
    result = await session.execute(count_stmt)

    return result.scalar_one()


def apply_sort(
    query: Select,
    sort: str | None,
    sort_map: dict[str, InstrumentedAttribute[Any] | Any],
    default: str,
) -> tuple[Select, InstrumentedAttribute[Any], bool]:
    """Apply ORDER BY from a sort key (prefix "-" = DESC).

    sort_map values must be raw columns (direction comes from the key prefix).
    Returns (query, applied_column, is_desc). The applied column is always
    non-None: if the requested sort key is invalid, the default column is used;
    if even the default is missing from sort_map, a ValueError is raised.
    """
    key = sort or default
    is_desc = key.startswith("-")
    col = sort_map.get(key.lstrip("-"))

    if col is None:
        col = sort_map.get(default.lstrip("-"))
        is_desc = default.startswith("-")

    if col is None:
        raise ValueError(
            f"Invalid sort key {key!r} and no valid default {default!r} in sort_map"
        )

    query = query.order_by(col.desc() if is_desc else col)

    return query, col, is_desc


def _encode_keyset_cursor(last_item: Any, sort_attr: str) -> str:
    value = getattr(last_item, sort_attr)

    if isinstance(value, Decimal):
        value = {"__decimal__": str(value)}

    payload = {"id": str(last_item.id), "v": value}

    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def _decode_keyset_cursor(cursor: str) -> tuple[UUID, Any]:
    try:
        payload = json.loads(base64.b64decode(cursor.encode("ascii")).decode("utf-8"))
        value = payload["v"]

        if isinstance(value, dict) and "__decimal__" in value:
            value = Decimal(value["__decimal__"])

        return UUID(payload["id"]), value
    except Exception as e:
        raise ValueError(f"Invalid cursor: {cursor!r}") from e


def paginate_query(
    query: Select,
    cursor: str | None,
    limit: int = 50,
    id_column: InstrumentedAttribute[Any] | None = None,
    sort_column: InstrumentedAttribute[Any] | None = None,
    sort_desc: bool = False,
) -> tuple[Select, int]:
    """Cursor pagination.

    - Plain mode (sort_column is None or the id column itself): cursor is the
      last row's id, filtering is id > cursor (or id < cursor for DESC).
    - Keyset mode (sort_column is a non-id column): cursor is base64 JSON
      {"id": ..., "v": sort_value}; filtering uses (sort_column, id) so sorted
      pages never overlap or skip rows.
    """
    effective_limit = min(limit, 200)

    if cursor:
        if id_column is None:
            raise ValueError("id_column is required when using cursor pagination")

        if sort_column is not None and sort_column is not id_column:
            cursor_id, cursor_val = _decode_keyset_cursor(cursor)

            if sort_desc:
                cond = or_(
                    sort_column < cursor_val,
                    and_(sort_column == cursor_val, id_column > cursor_id),
                )
            else:
                cond = or_(
                    sort_column > cursor_val,
                    and_(sort_column == cursor_val, id_column > cursor_id),
                )

            query = query.where(cond)
        else:
            try:
                cursor_uuid = UUID(cursor)
            except ValueError as e:
                raise ValueError(f"Invalid cursor: {cursor!r}") from e

            if sort_desc:
                query = query.where(id_column < cursor_uuid)
            else:
                query = query.where(id_column > cursor_uuid)

    if (
        sort_column is not None
        and id_column is not None
        and sort_column is not id_column
    ):
        query = query.order_by(
            sort_column.desc() if sort_desc else sort_column,
            id_column,
        )
    elif id_column is not None:
        query = query.order_by(id_column.desc() if sort_desc else id_column)

    query = query.limit(effective_limit + 1)

    return query, effective_limit


def build_cursor_response(
    items: list[Any], limit: int, sort_attr: str | None = None
) -> tuple[list[Any], str | None]:
    next_cursor = None

    if len(items) > limit:
        items = items[:limit]

        if items:
            if sort_attr is not None:
                next_cursor = _encode_keyset_cursor(items[-1], sort_attr)
            else:
                next_cursor = str(items[-1].id)

    return items, next_cursor
