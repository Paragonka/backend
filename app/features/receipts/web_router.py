# DEPRECATED - server-rendered HTML/HTMX routes kept only for backwards compatibility.
# The SPA + JSON API are the supported entry points; do not add features here.
import json

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette import status

from app.core.uow import AppUnitOfWork
from app.features.clients.service import ClientService
from app.features.orders.service import OrderService
from app.features.products.service import ProductService
from app.features.receipts.schemas import ReceiptItemCreate
from app.features.receipts.service import ReceiptParseError, ReceiptService
from app.features.users.models import User
from app.shared.dependencies import get_current_user, get_uow, verify_org_access
from app.shared.templates import templates
from app.shared.web_forms import empty_to_none, normalize_datetime

router = APIRouter(tags=["receipts-web"])

logger = structlog.get_logger(__name__)


@router.post("/{org_id}/receipts/upload-jpk", response_class=HTMLResponse)
async def upload_jpk_receipt(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    file: UploadFile = File(...),
):
    """Upload a JPK JSON receipt file, parse it, and create a receipt."""
    content = await file.read()

    try:
        json_data = json.loads(content)
    except (json.JSONDecodeError, ValueError) as exc:
        snippet = None

        try:
            snippet = (
                content[:300].decode("utf-8", errors="replace")
                if isinstance(content, (bytes, bytearray))
                else str(content)[:300]
            )
        except Exception:
            snippet = "<unreadable>"

        logger.info(
            "jpk_parse_error",
            org_id=org_id,
            filename=getattr(file, "filename", None),
            content_len=len(content) if content is not None else 0,
            snippet=snippet,
            error=str(exc),
        )

        return templates.TemplateResponse(
            request,
            "features/receipts/upload_error.html",
            {"org_id": org_id, "error": "Неверный формат JSON"},
            status_code=400,
        )

    service = ReceiptService(uow)

    try:
        receipt = await service.create_receipt_from_jpk(org_id, json_data)
    except ReceiptParseError as e:
        return templates.TemplateResponse(
            request,
            "features/receipts/upload_error.html",
            {
                "org_id": org_id,
                "error": e.message,
                "details": e.details,
                "format": e.format_detected,
            },
            status_code=400,
        )

    return Response(
        status_code=200,
        headers={"HX-Redirect": f"/app/{org_id}/receipts/{receipt.id}"},
    )


@router.get("/{org_id}/receipts/upload", response_class=HTMLResponse)
async def receipts_upload_page(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    """JPK upload page - drag & drop or file select."""

    return templates.TemplateResponse(
        request,
        "features/receipts/upload.html",
        {"org_id": org_id},
    )


RECEIPTS_FILTER_FIELDS = [
    {"name": "date_from", "label": "Дата с", "type": "date"},
    {"name": "date_to", "label": "Дата по", "type": "date"},
    {
        "name": "source",
        "label": "Источник",
        "type": "text",
        "placeholder": "manual, jpk...",
    },
]


@router.get("/{org_id}/receipts", response_class=HTMLResponse)
async def receipts_list_page(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    filter_date_from: str | None = Query(None, alias="filter[date_from]"),
    filter_date_to: str | None = Query(None, alias="filter[date_to]"),
    filter_source: str | None = Query(None, alias="filter[source]"),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    service = ReceiptService(uow)
    receipts, next_cursor = await service.get_filtered(
        org_id=org_id,
        cursor=cursor,
        limit=limit,
        date_from=filter_date_from,
        date_to=filter_date_to,
        source=filter_source,
    )

    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(
            request,
            "features/receipts/_list_fragment.html",
            {"receipts": receipts, "org_id": org_id, "next_cursor": next_cursor},
        )

    return templates.TemplateResponse(
        request,
        "features/receipts/list.html",
        {
            "receipts": receipts,
            "org_id": org_id,
            "next_cursor": next_cursor,
            "filter_fields": RECEIPTS_FILTER_FIELDS,
            "current_filters": {
                "date_from": filter_date_from or "",
                "date_to": filter_date_to or "",
                "source": filter_source or "",
            },
        },
    )


@router.get("/{org_id}/receipts/create", response_class=HTMLResponse)
async def receipts_create_page(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    client_service = ClientService(uow)
    order_service = OrderService(uow)
    product_service = ProductService(uow)
    clients = await client_service.get_org_clients(org_id)
    orders = await order_service.get_org_orders(org_id)
    products = await product_service.get_org_products(org_id)

    return templates.TemplateResponse(
        request,
        "features/receipts/create.html",
        {"org_id": org_id, "clients": clients, "orders": orders, "products": products},
    )


@router.post("/{org_id}/receipts/create")
async def create_receipt(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    form = await request.form()
    service = ReceiptService(uow)
    client_id = empty_to_none(str(form.get("client_id") or ""))
    order_id = empty_to_none(str(form.get("order_id") or ""))
    receipt_date = normalize_datetime(str(form.get("receipt_date", "")))

    product_ids = form.getlist("product_id")
    names = form.getlist("item_name")
    prices = form.getlist("item_price")
    qties = form.getlist("item_qty")

    items_data = []

    for pid, name, price, qty in zip(product_ids, names, prices, qties, strict=False):
        if str(name).strip():
            from decimal import Decimal

            items_data.append(
                ReceiptItemCreate(
                    product_id=str(pid) if pid else None,
                    name=str(name),
                    price=Decimal(str(price or 0)),
                    qty=Decimal(str(qty or 1)),
                )
            )

    try:
        receipt = await service.create_receipt(
            org_id=org_id,
            items_data=items_data,
            client_id=client_id,
            order_id=order_id,
            receipt_date=receipt_date,
            source=str(form.get("source", "")) or None,
            notes=str(form.get("notes", "")) or None,
        )
    except ValueError:
        return RedirectResponse(url=f"/app/{org_id}/receipts/create", status_code=302)

    return RedirectResponse(url=f"/app/{org_id}/receipts/{receipt.id}", status_code=302)


@router.get("/{org_id}/receipts/{receipt_id}", response_class=HTMLResponse)
async def receipt_detail_page(
    request: Request,
    receipt_id: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = ReceiptService(uow)
    receipt = await service.get_receipt_in_org(receipt_id, org_id)

    if not receipt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found"
        )

    items = await service.get_items(receipt.id)

    return templates.TemplateResponse(
        request,
        "features/receipts/detail.html",
        {"receipt": receipt, "items": items, "org_id": org_id},
    )


@router.post("/{org_id}/receipts/{receipt_id}/delete")
async def delete_receipt(
    request: Request,
    receipt_id: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = ReceiptService(uow)
    deleted = await service.delete_receipt_in_org(receipt_id, org_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found"
        )

    return RedirectResponse(url=f"/app/{org_id}/receipts", status_code=302)
