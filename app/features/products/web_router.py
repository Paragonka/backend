# DEPRECATED - server-rendered HTML/HTMX routes kept only for backwards compatibility.
# The SPA + JSON API are the supported entry points; do not add features here.
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette import status

from app.core.uow import AppUnitOfWork
from app.features.eav.service import EavAttributeService
from app.features.media.service import MediaService
from app.features.products.service import ProductService
from app.features.users.models import User
from app.shared.constants import (
    ENTITY_TYPE_PRODUCT,
    PRODUCT_TYPE_GOOD,
    PRODUCT_TYPE_MATERIAL,
    PRODUCT_TYPE_SERVICE,
)
from app.shared.dependencies import get_current_user, get_uow, verify_org_access
from app.shared.feature_flags import RequireFeatureCsv
from app.shared.templates import templates
from app.shared.web_forms import extract_local_fields, parse_eav_filters

router = APIRouter(tags=["products-web"])

# CSV import UI - enabled only when FEATURE_CSV=true (see config.feature_csv)
csv_web_router = APIRouter(tags=["products-web"])

FILTER_FIELDS = [
    {"name": "name", "label": "Название", "type": "text", "placeholder": "Название"},
    {
        "name": "product_type",
        "label": "Тип",
        "type": "select",
        "placeholder": "Все",
        "options": [
            {"value": PRODUCT_TYPE_GOOD, "label": "Товар"},
            {"value": PRODUCT_TYPE_SERVICE, "label": "Услуга"},
            {"value": PRODUCT_TYPE_MATERIAL, "label": "Сырьё / Материал"},
        ],
    },
    {
        "name": "is_active",
        "label": "Активен",
        "type": "select",
        "placeholder": "Все",
        "options": [
            {"value": "true", "label": "Да"},
            {"value": "false", "label": "Нет"},
        ],
    },
]


@router.get("/{org_id}/products", response_class=HTMLResponse)
async def products_list_page(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    filter_name: str | None = Query(None, alias="filter[name]"),
    filter_category: str | None = Query(None, alias="filter[category]"),
    filter_product_type: str | None = Query(None, alias="filter[product_type]"),
    filter_is_active: str | None = Query(None, alias="filter[is_active]"),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    product_service = ProductService(uow)

    eav_filters_raw = parse_eav_filters(request.query_params)

    is_active = None

    if filter_is_active == "true":
        is_active = True
    elif filter_is_active == "false":
        is_active = False

    products, next_cursor, _total = await product_service.get_filtered(
        org_id=org_id,
        cursor=cursor,
        limit=limit,
        name=filter_name,
        category=filter_category,
        product_type=filter_product_type,
        is_active=is_active,
        eav_filters=eav_filters_raw or None,
    )

    eav_attributes = await EavAttributeService(uow).get_by_entity_code(
        org_id, entity_code=ENTITY_TYPE_PRODUCT
    )

    current_filters = {
        "name": filter_name or "",
        "category": filter_category or "",
        "product_type": filter_product_type or "",
        "is_active": filter_is_active or "",
    }

    current_eav = eav_filters_raw

    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(
            request,
            "features/products/_list_fragment.html",
            {"products": products, "org_id": org_id, "next_cursor": next_cursor},
        )

    return templates.TemplateResponse(
        request,
        "features/products/list.html",
        {
            "products": products,
            "org_id": org_id,
            "filter_fields": FILTER_FIELDS,
            "current_filters": current_filters,
            "eav_attributes": eav_attributes,
            "current_eav": current_eav,
            "next_cursor": next_cursor,
        },
    )


@router.get("/{org_id}/products/create", response_class=HTMLResponse)
async def products_create_page(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    products = await ProductService(uow).get_org_products(org_id)

    return templates.TemplateResponse(
        request,
        "features/products/create.html",
        {"org_id": org_id, "products": products, "product_components": []},
    )


def _extract_product_components(form) -> list[dict[str, object]]:
    product_ids = form.getlist("component_product_id")
    quantities = form.getlist("component_quantity")
    result = []

    for product_id, quantity in zip(product_ids, quantities, strict=False):
        product_id = str(product_id).strip()
        quantity = str(quantity).strip()

        if not product_id:
            continue

        try:
            parsed_quantity = Decimal(quantity)
        except (ArithmeticError, ValueError) as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Количество продукта в составе должно быть числом",
            ) from e

        result.append({"product_id": product_id, "quantity": parsed_quantity})

    return result


async def _upload_form_photos(
    form, uow: AppUnitOfWork, org_id: str, entity_type: str, entity_id: str
) -> None:
    media_service = MediaService(uow)

    for file in form.getlist("photos"):
        if not getattr(file, "filename", None):
            continue

        await media_service.add_photo_to_entity(
            org_id=org_id,
            entity_type=entity_type,
            entity_id=entity_id,
            file_bytes=await file.read(),
            content_type=file.content_type or "image/jpeg",
            filename=file.filename or "photo.jpg",
        )


@router.post("/{org_id}/products/create")
async def create_product(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    form = await request.form()
    service = ProductService(uow)

    stock_qty = form.get("stock_qty")
    product = await service.create_product(
        org_id=org_id,
        name=str(form.get("name", "")),
        category=str(form.get("category", "")),
        unit=str(form.get("unit", "шт")),
        product_type=str(form.get("product_type", PRODUCT_TYPE_GOOD)),
        price=Decimal(str(form.get("price", 0))),
        cost_price=Decimal(str(form.get("cost_price", 0))),
        stock_qty=Decimal(str(stock_qty)) if stock_qty else None,
        track_inventory=form.get("track_inventory") == "on",
        is_sellable=form.get("is_sellable") == "on",
        local_fields=extract_local_fields(form),
        components=_extract_product_components(form),
    )
    await _upload_form_photos(form, uow, org_id, "products", str(product.id))

    return RedirectResponse(url=f"/app/{org_id}/products", status_code=302)


@router.get("/{org_id}/products/{product_id}/edit", response_class=HTMLResponse)
async def products_edit_page(
    request: Request,
    product_id: str,
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

    return templates.TemplateResponse(
        request,
        "features/products/edit.html",
        {
            "product": product,
            "org_id": org_id,
            "local_fields": product.local_fields or {},
            "photos": product.photos or [],
            "products": await service.get_org_products(org_id),
            "product_components": product.components or [],
        },
    )


@router.get("/{org_id}/products/{product_id}/edit-form", response_class=HTMLResponse)
async def products_edit_form_fragment(
    request: Request,
    product_id: str,
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

    return templates.TemplateResponse(
        request,
        "features/products/edit_form.html",
        {
            "product": product,
            "org_id": org_id,
            "local_fields": product.local_fields or {},
            "photos": product.photos or [],
            "products": await service.get_org_products(org_id),
            "product_components": product.components or [],
        },
    )


@router.post("/{org_id}/products/{product_id}/edit")
async def update_product(
    request: Request,
    product_id: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    form = await request.form()
    service = ProductService(uow)

    stock_qty = form.get("stock_qty")
    product = await service.update_product_in_org(
        product_id,
        org_id,
        name=str(form.get("name", "")),
        category=str(form.get("category", "")),
        unit=str(form.get("unit", "шт")),
        product_type=str(form.get("product_type", PRODUCT_TYPE_GOOD)),
        price=Decimal(str(form.get("price", 0))),
        cost_price=Decimal(str(form.get("cost_price", 0))),
        stock_qty=Decimal(str(stock_qty)) if stock_qty else None,
        track_inventory=form.get("track_inventory") == "on",
        is_sellable=form.get("is_sellable") == "on",
        is_active=form.get("is_active") == "on",
        local_fields=extract_local_fields(form),
        components=_extract_product_components(form),
    )

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    await _upload_form_photos(form, uow, org_id, "products", str(product.id))

    return RedirectResponse(url=f"/app/{org_id}/products", status_code=302)


@router.post("/{org_id}/products/{product_id}/delete")
async def delete_product(
    request: Request,
    product_id: str,
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

    return RedirectResponse(url=f"/app/{org_id}/products", status_code=302)


@csv_web_router.get("/{org_id}/products/import", response_class=HTMLResponse)
async def products_import_page(
    request: Request,
    require_csv: RequireFeatureCsv,
    org_id: str = Depends(verify_org_access),
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request,
        "features/products/import.html",
        {"org_id": org_id},
    )


@csv_web_router.post("/{org_id}/products/import", response_class=HTMLResponse)
async def products_import_upload(
    request: Request,
    require_csv: RequireFeatureCsv,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    file: UploadFile = File(...),
):
    from app.shared.csv_import import CsvImportResult, parse_bool, parse_csv

    content = await file.read()
    result = CsvImportResult()

    if len(content) > 5 * 1024 * 1024:
        result.add_error(0, "Файл слишком большой (макс 5 MB)")

        return templates.TemplateResponse(
            request,
            "features/products/import.html",
            {"org_id": org_id, "result": result, "filename": file.filename},
        )

    try:
        _, rows = parse_csv(content)
    except ValueError as e:
        result.add_error(0, str(e))

        return templates.TemplateResponse(
            request,
            "features/products/import.html",
            {"org_id": org_id, "result": result, "filename": file.filename},
        )

    if len(rows) > 5000:
        result.add_error(0, "Максимум 5000 строк за один импорт")

        return templates.TemplateResponse(
            request,
            "features/products/import.html",
            {"org_id": org_id, "result": result, "filename": file.filename},
        )

    service = ProductService(uow)

    for i, row in enumerate(rows, start=2):
        try:
            await service.create_product(
                org_id=org_id,
                name=str(row.get("name", "")),
                category=str(row.get("category", "")),
                unit=str(row.get("unit", "шт")),
                product_type=str(row.get("product_type", PRODUCT_TYPE_GOOD)),
                price=Decimal(str(row.get("price", 0))),
                cost_price=Decimal(str(row.get("cost_price", 0))),
                stock_qty=Decimal(str(row["stock_qty"]))
                if row.get("stock_qty")
                else None,
                track_inventory=parse_bool(row.get("track_inventory", "false")),
                is_sellable=parse_bool(row.get("is_sellable", "true")),
                is_active=parse_bool(row.get("is_active", "true")),
            )
            result.created += 1
        except Exception as e:
            result.add_error(i, str(e))

    return templates.TemplateResponse(
        request,
        "features/products/import.html",
        {"org_id": org_id, "result": result, "filename": file.filename},
    )


router.include_router(csv_web_router)
