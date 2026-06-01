# DEPRECATED - server-rendered HTML/HTMX routes kept only for backwards compatibility.
# The SPA + JSON API are the supported entry points; do not add features here.
import calendar
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette import status

from app.core.uow import AppUnitOfWork
from app.features.clients.service import ClientService
from app.features.orders.service import OrderService
from app.features.products.service import ProductService
from app.features.users.models import User
from app.shared.constants import (
    ORDER_STATUS_CANCELLED,
    ORDER_STATUS_CONFIRMED,
    ORDER_STATUS_DONE,
    ORDER_STATUS_DRAFT,
)
from app.shared.dependencies import get_current_user, get_uow, verify_org_access
from app.shared.templates import templates

router = APIRouter(tags=["orders-web"])

ORDERS_FILTER_FIELDS = [
    {
        "name": "status",
        "label": "Статус",
        "type": "select",
        "placeholder": "Все",
        "options": [
            {"value": ORDER_STATUS_DRAFT, "label": "Черновик"},
            {"value": ORDER_STATUS_CONFIRMED, "label": "Подтверждён"},
            {"value": ORDER_STATUS_DONE, "label": "Выполнен"},
            {"value": ORDER_STATUS_CANCELLED, "label": "Отменён"},
        ],
    },
    {"name": "execution_date_from", "label": "Дата исполнения с", "type": "date"},
    {"name": "execution_date_to", "label": "Дата исполнения по", "type": "date"},
    {"name": "created_from", "label": "Создан с", "type": "date"},
    {"name": "created_to", "label": "Создан по", "type": "date"},
    {
        "name": "deleted",
        "label": "Удалённые",
        "type": "select",
        "placeholder": "Активные",
        "options": [
            {"value": "true", "label": "Показать удалённые"},
        ],
    },
]


@router.get("/{org_id}/orders", response_class=HTMLResponse)
async def orders_list_page(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    filter_status: str | None = Query(None, alias="filter[status]"),
    filter_execution_date_from: str | None = Query(
        None, alias="filter[execution_date_from]"
    ),
    filter_execution_date_to: str | None = Query(
        None, alias="filter[execution_date_to]"
    ),
    filter_deleted: str | None = Query(None, alias="filter[deleted]"),
    filter_created_from: str | None = Query(None, alias="filter[created_from]"),
    filter_created_to: str | None = Query(None, alias="filter[created_to]"),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    service = OrderService(uow)
    include_deleted = filter_deleted == "true"
    orders, next_cursor, _total, _client_names, _items_map = await service.get_filtered(
        org_id=org_id,
        cursor=cursor,
        limit=limit,
        status=filter_status,
        execution_date_from=filter_execution_date_from,
        execution_date_to=filter_execution_date_to,
        created_from=filter_created_from,
        created_to=filter_created_to,
        include_deleted=include_deleted,
    )
    user_ids = {o.created_by for o in orders if o.created_by} | {
        o.updated_by for o in orders if o.updated_by
    }
    user_names = await service.get_user_names(user_ids)

    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(
            request,
            "features/orders/_list_fragment.html",
            {"orders": orders, "org_id": org_id, "next_cursor": next_cursor},
        )

    return templates.TemplateResponse(
        request,
        "features/orders/list.html",
        {
            "orders": orders,
            "org_id": org_id,
            "next_cursor": next_cursor,
            "filter_fields": ORDERS_FILTER_FIELDS,
            "current_filters": {
                "status": filter_status or "",
                "execution_date_from": filter_execution_date_from or "",
                "execution_date_to": filter_execution_date_to or "",
                "deleted": filter_deleted or "",
                "created_from": filter_created_from or "",
                "created_to": filter_created_to or "",
            },
            "user_names": user_names,
        },
    )


@router.get("/{org_id}/orders/create", response_class=HTMLResponse)
async def orders_create_page(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    execution_date: str | None = None,
):
    client_service = ClientService(uow)
    product_service = ProductService(uow)
    clients = await client_service.get_org_clients(org_id)
    products = await product_service.get_org_products(org_id)

    return templates.TemplateResponse(
        request,
        "features/orders/create.html",
        {
            "org_id": org_id,
            "clients": clients,
            "products": products,
            "execution_date": execution_date or "",
        },
    )


@router.post("/{org_id}/orders/create")
async def create_order(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    form = await request.form()
    service = OrderService(uow)
    client_id = str(form.get("client_id") or "")

    if client_id == "":
        client_id = None

    raw_date = str(form.get("execution_date", ""))

    execution_date = raw_date.replace("T", " ") if "T" in raw_date else raw_date

    keys = form.getlist("lf_key")
    values = form.getlist("lf_value")
    local_fields = {}

    for k, v in zip(keys, values, strict=False):
        key = str(k).strip()

        if key:
            local_fields[key] = str(v).strip()

    product_ids = form.getlist("product_id")
    names = form.getlist("item_name")
    prices = form.getlist("item_price")
    qties = form.getlist("item_qty")
    items_data = []

    for pid, name, price, qty in zip(product_ids, names, prices, qties, strict=False):
        if pid:
            items_data.append(
                {
                    "product_id": str(pid),
                    "name": str(name),
                    "price": Decimal(str(price or 0)),
                    "qty": Decimal(str(qty or 1)),
                }
            )

    await service.create_order(
        org_id=org_id,
        client_id=client_id,
        execution_date=execution_date,
        notes=str(form.get("notes", "")),
        local_fields=local_fields,
        items=items_data,
        created_by=current_user.id,
    )

    return RedirectResponse(url=f"/app/{org_id}/orders", status_code=302)


@router.get("/{org_id}/orders/{order_id}", response_class=HTMLResponse)
async def order_detail_page(
    request: Request,
    order_id: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = OrderService(uow)
    detail = await service.get_order_detail(order_id, org_id)

    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
        )

    product_service = ProductService(uow)
    products = await product_service.get_org_products(org_id)

    referer = request.headers.get("referer", "")
    back_url = (
        referer if referer and f"/app/{org_id}" in referer else f"/app/{org_id}/orders"
    )

    return templates.TemplateResponse(
        request,
        "features/orders/detail.html",
        {
            "order": detail["order"],
            "items": detail["items"],
            "org_id": org_id,
            "back_url": back_url,
            "client_name": detail["client_name"],
            "creator_name": detail["creator_name"],
            "updater_name": detail["updater_name"],
            "products": products,
        },
    )


@router.get("/{org_id}/orders/{order_id}/fragment", response_class=HTMLResponse)
async def order_detail_fragment(
    request: Request,
    order_id: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = OrderService(uow)
    detail = await service.get_order_detail(order_id, org_id)

    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
        )

    return templates.TemplateResponse(
        request,
        "features/orders/_order_modal.html",
        {
            "order": detail["order"],
            "items": detail["items"],
            "org_id": org_id,
            "client_name": detail["client_name"],
        },
    )


@router.post("/{org_id}/orders/{order_id}/items/add")
async def add_order_item(
    request: Request,
    order_id: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    form = await request.form()
    service = OrderService(uow)
    await service.add_item(
        order_id=order_id,
        product_id=str(form.get("product_id", "")),
        name=str(form.get("name", "")),
        price=Decimal(str(form.get("price", 0))),
        qty=Decimal(str(form.get("qty", 1))),
        org_id=org_id,
    )

    return RedirectResponse(url=f"/app/{org_id}/orders/{order_id}", status_code=302)


@router.post("/{org_id}/orders/{order_id}/items/{item_id}/delete")
async def delete_order_item(
    request: Request,
    order_id: str,
    item_id: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = OrderService(uow)
    await service.remove_item(order_id=order_id, item_id=item_id, org_id=org_id)

    return RedirectResponse(url=f"/app/{org_id}/orders/{order_id}", status_code=302)


@router.post("/{org_id}/orders/{order_id}/items/{item_id}/edit")
async def edit_order_item(
    request: Request,
    order_id: str,
    item_id: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    form = await request.form()
    service = OrderService(uow)
    await service.update_item(
        order_id=order_id,
        item_id=item_id,
        org_id=org_id,
        name=str(form.get("name", "")),
        price=Decimal(str(form.get("price", 0))),
        qty=Decimal(str(form.get("qty", 1))),
    )

    return RedirectResponse(url=f"/app/{org_id}/orders/{order_id}", status_code=302)


@router.post("/{org_id}/orders/{order_id}/writeoff")
async def write_off_materials(
    request: Request,
    order_id: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    form = await request.form()
    service = OrderService(uow)
    items = await service.get_items(order_id, org_id=org_id)
    qties = form.getlist("wo_qty")

    qty_by_item = {
        str(item.id): Decimal(str(qty or 0))
        for item, qty in zip(items, qties, strict=False)
    }

    await service.write_off_bulk(order_id, org_id, qty_by_item)

    return RedirectResponse(url=f"/app/{org_id}/orders/{order_id}", status_code=302)


@router.get("/{org_id}/calendar", response_class=HTMLResponse)
async def calendar_page(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    month: str | None = Query(None),
    view: str = Query("month"),
    date: str | None = Query(None),
):
    service = OrderService(uow)
    now = datetime.now()

    if month:
        year_s, month_s = month.split("-")
        year, mon = int(year_s), int(month_s)
    else:
        year, mon = now.year, now.month

    if view == "day" and date:
        date_from = date
        date_to = date
    else:
        _, last_day = calendar.monthrange(year, mon)
        date_from = f"{year:04d}-{mon:02d}-01"
        date_to = f"{year:04d}-{mon:02d}-{last_day:02d}"

    orders = await service.get_by_date_range(org_id, date_from, date_to)

    client_ids = {o.client_id for o in orders if o.client_id}

    client_names = await service.get_client_names(client_ids)

    cal = calendar.monthcalendar(year, mon)

    month_name = f"{year:04d}-{mon:02d}"

    prev_month = f"{year:04d}-{mon - 1:02d}" if mon > 1 else f"{year - 1:04d}-12"
    next_month = f"{year:04d}-{mon + 1:02d}" if mon < 12 else f"{year + 1:04d}-01"

    return templates.TemplateResponse(
        request,
        "features/orders/calendar.html",
        {
            "org_id": org_id,
            "orders": orders,
            "calendar": cal,
            "year": year,
            "month": mon,
            "month_name": month_name,
            "prev_month": prev_month,
            "next_month": next_month,
            "view": view,
            "current_date": date or month_name,
            "client_names": client_names,
        },
    )


@router.post("/{org_id}/orders/{order_id}/status")
async def change_order_status(
    request: Request,
    order_id: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    form = await request.form()
    service = OrderService(uow)
    updated = await service.change_status_in_org(
        order_id,
        org_id,
        str(form.get("status", ORDER_STATUS_DRAFT)),
        updated_by=current_user.id,
    )

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
        )

    return RedirectResponse(url=f"/app/{org_id}/orders/{order_id}", status_code=302)


@router.post("/{org_id}/orders/{order_id}/delete")
async def delete_order(
    request: Request,
    order_id: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = OrderService(uow)
    deleted = await service.delete_order_in_org(
        order_id, org_id, updated_by=current_user.id
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
        )

    return RedirectResponse(url=f"/app/{org_id}/orders", status_code=302)
