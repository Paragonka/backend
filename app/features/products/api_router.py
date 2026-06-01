from decimal import Decimal
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)

from app.core.uow import AppUnitOfWork
from app.features.products.schemas import (
    PaginatedProducts,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from app.features.products.service import ProductService
from app.features.users.models import User
from app.shared.constants import PRODUCT_TYPE_GOOD, PRODUCT_TYPES
from app.shared.dependencies import get_current_user, get_uow, verify_org_access
from app.shared.exceptions import AppHttpException
from app.shared.feature_flags import RequireFeatureCsv

router = APIRouter(prefix="/api/v1/products", tags=["products"])

# TODO: CSV feature routes - enabled only when FEATURE_CSV=true.
csv_router = APIRouter(tags=["products"])


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = ProductService(uow)
    product = await service.create_product(
        org_id=org_id,
        name=data.name,
        category=data.category,
        unit=data.unit,
        product_type=data.product_type,
        price=data.price,
        cost_price=data.cost_price,
        stock_qty=data.stock_qty,
        track_inventory=data.track_inventory,
        is_sellable=data.is_sellable,
        is_active=data.is_active,
        custom_fields=data.custom_fields,
        local_fields=data.local_fields,
        components=data.components,
    )

    return ProductResponse.model_validate(product)


@router.get("", response_model=PaginatedProducts)
async def list_products(
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    sort: str | None = Query(None),
    filter_name: str | None = Query(None, alias="filter[name]"),
    filter_category: str | None = Query(None, alias="filter[category]"),
    filter_product_type: str | None = Query(None, alias="filter[product_type]"),
    filter_is_active: bool | None = Query(None, alias="filter[is_active]"),
):
    service = ProductService(uow)
    products, next_cursor, total = await service.get_filtered(
        org_id=org_id,
        cursor=cursor,
        limit=limit,
        name=filter_name,
        category=filter_category,
        product_type=filter_product_type,
        is_active=filter_is_active,
        sort=sort,
    )

    return PaginatedProducts(
        data=[ProductResponse.model_validate(p) for p in products],
        next_cursor=next_cursor,
        total=total,
    )


@router.get("/all", response_model=list[ProductResponse])
async def list_all_products(
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = ProductService(uow)
    products = await service.get_org_products(org_id)

    return [ProductResponse.model_validate(p) for p in products]


@csv_router.get("/export.csv")
async def export_products_csv(
    require_csv: RequireFeatureCsv,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    from app.shared.csv_export import (
        add_custom_columns,
        ensure_export_limit,
        rows_to_csv,
    )

    service = ProductService(uow)
    products = await service.get_org_products(org_id)

    rows = []

    for p in products:
        row = {
            "name": p.name,
            "category": p.category,
            "unit": p.unit,
            "product_type": p.product_type,
            "price": p.price,
            "cost_price": p.cost_price,
            "stock_qty": p.stock_qty if p.stock_qty is not None else "",
            "track_inventory": p.track_inventory,
            "is_sellable": p.is_sellable,
            "is_active": p.is_active,
        }
        add_custom_columns(row, p.custom_fields)
        rows.append(row)

    try:
        ensure_export_limit(rows)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    headers = [
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
    ]

    custom_keys = sorted({k for r in rows for k in r if k.startswith("cf_")})
    csv_str = rows_to_csv(rows, headers + custom_keys)

    return Response(
        content=csv_str.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="products.csv"'},
    )


@csv_router.post("/import", status_code=status.HTTP_200_OK)
async def import_products(
    require_csv: RequireFeatureCsv,
    file: UploadFile,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    mode: str = Query("create", pattern="^(create|upsert)$"),
):
    from app.shared.csv_import import (
        PRODUCT_CSV_COLUMNS,
        CsvImportResult,
        parse_bool,
        parse_csv,
        validate_csv_columns,
    )

    content = await file.read()
    result = CsvImportResult()

    try:
        headers, rows = parse_csv(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    col_errors = validate_csv_columns(headers, PRODUCT_CSV_COLUMNS, "product")

    if col_errors:
        raise HTTPException(status_code=400, detail="; ".join(col_errors))

    if len(rows) > 5000:
        raise HTTPException(status_code=400, detail="Maximum 5000 rows per import")

    service = ProductService(uow)

    for i, row in enumerate(rows, start=2):
        try:
            custom_fields = _parse_custom_fields(row)
            product_type = str(row.get("product_type", PRODUCT_TYPE_GOOD))

            if product_type not in PRODUCT_TYPES:
                result.add_error(
                    i,
                    f"Invalid product_type: '{product_type}'. "
                    f"Must be one of: {PRODUCT_TYPES}",
                )

                continue

            if mode == "upsert":
                _, status_out = await service.upsert_product(
                    org_id=org_id,
                    name=str(row.get("name", "")),
                    category=str(row.get("category", "")),
                    unit=str(row.get("unit", "шт")),
                    product_type=str(row.get("product_type", PRODUCT_TYPE_GOOD)),
                    price=Decimal(str(float(row.get("price", 0)))),
                    cost_price=Decimal(str(float(row.get("cost_price", 0)))),
                    stock_qty=Decimal(str(float(row["stock_qty"])))
                    if row.get("stock_qty")
                    else None,
                    track_inventory=parse_bool(row.get("track_inventory", "false")),
                    is_sellable=parse_bool(row.get("is_sellable", "true")),
                    is_active=parse_bool(row.get("is_active", "true")),
                    custom_fields=custom_fields,
                )

                if status_out == "created":
                    result.created += 1
                else:
                    result.updated += 1
            else:
                await service.create_product(
                    org_id=org_id,
                    name=str(row.get("name", "")),
                    category=str(row.get("category", "")),
                    unit=str(row.get("unit", "шт")),
                    product_type=str(row.get("product_type", PRODUCT_TYPE_GOOD)),
                    price=Decimal(str(float(row.get("price", 0)))),
                    cost_price=Decimal(str(float(row.get("cost_price", 0)))),
                    stock_qty=Decimal(str(float(row["stock_qty"])))
                    if row.get("stock_qty")
                    else None,
                    track_inventory=parse_bool(row.get("track_inventory", "false")),
                    is_sellable=parse_bool(row.get("is_sellable", "true")),
                    is_active=parse_bool(row.get("is_active", "true")),
                    custom_fields=custom_fields,
                )
                result.created += 1
        except AppHttpException as e:
            result.add_error(i, e.message)
        except (ValueError, TypeError, KeyError) as e:
            result.add_error(i, str(e))

    return {
        "imported": result.imported,
        "created": result.created,
        "updated": result.updated,
        "errors": result.errors,
    }


def _parse_custom_fields(row: dict) -> dict | None:
    raw = row.get("custom_fields")

    if not raw:
        return None

    import json

    try:
        parsed = json.loads(str(raw))

        if not isinstance(parsed, dict):
            raise ValueError("custom_fields must be a JSON object")

        return parsed
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid custom_fields: {e}") from e


router.include_router(csv_router)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = ProductService(uow)
    product = await service.get_product_in_org(product_id, org_id)

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    return ProductResponse.model_validate(product)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    data: ProductUpdate,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = ProductService(uow)
    product = await service.update_product_in_org(
        product_id, org_id, **data.model_dump(exclude_none=True)
    )

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    return ProductResponse.model_validate(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = ProductService(uow)
    deleted = await service.delete_product_in_org(product_id, org_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
