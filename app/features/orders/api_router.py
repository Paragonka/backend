from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.uow import AppUnitOfWork
from app.features.orders.schemas import (
    OrderCreate,
    OrderItemCreate,
    OrderItemResponse,
    OrderItemUpdate,
    OrderResponse,
    PaginatedOrders,
    StatusUpdate,
    WriteOffItemCreate,
    WriteOffResponse,
)
from app.features.orders.service import OrderService
from app.features.users.models import User
from app.shared.dependencies import get_current_user, get_uow, verify_org_access
from app.shared.feature_flags import RequireFeatureCsv

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])

# TODO: CSV export - enabled only when FEATURE_CSV=true.
csv_router = APIRouter(tags=["orders"])


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    data: OrderCreate,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = OrderService(uow)
    order = await service.create_order(
        org_id=org_id,
        client_id=data.client_id,
        execution_date=data.execution_date,
        notes=data.notes,
        local_fields=data.local_fields,
        custom_fields=data.custom_fields,
        items=data.items if data.items else None,
        created_by=current_user.id,
    )
    items = await service.get_items(order.id)

    return await service._build_order_response(order, items)


@router.get("", response_model=PaginatedOrders)
async def list_orders(
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    sort: str | None = Query(None),
    filter_status: str | None = Query(None, alias="filter[status]"),
    filter_execution_date_from: str | None = Query(
        None, alias="filter[execution_date_from]"
    ),
    filter_execution_date_to: str | None = Query(
        None, alias="filter[execution_date_to]"
    ),
    include_deleted: bool = Query(False),
):
    service = OrderService(uow)
    orders, next_cursor, total, client_names, items_map = await service.get_filtered(
        org_id=org_id,
        cursor=cursor,
        limit=limit,
        status=filter_status,
        execution_date_from=filter_execution_date_from,
        execution_date_to=filter_execution_date_to,
        sort=sort,
        include_deleted=include_deleted,
    )
    enriched = []

    for o in orders:
        base = OrderResponse.model_validate(o)
        enriched.append(
            OrderResponse(
                id=base.id,
                org_id=base.org_id,
                client_id=base.client_id,
                client_name=client_names.get(o.id, ""),
                status=base.status,
                total=base.total,
                execution_date=base.execution_date,
                notes=base.notes,
                photos=base.photos,
                local_fields=base.local_fields,
                custom_fields=base.custom_fields,
                is_deleted=base.is_deleted,
                items=[
                    OrderItemResponse.model_validate(i) for i in items_map.get(o.id, [])
                ],
            )
        )

    return PaginatedOrders(
        data=enriched,
        next_cursor=next_cursor,
        total=total,
    )


@router.get("/all", response_model=list[OrderResponse])
async def list_all_orders(
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = OrderService(uow)
    orders = await service.get_org_orders(org_id)

    return [OrderResponse.model_validate(o) for o in orders]


@csv_router.get("/export.csv")
async def export_orders_csv(
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

    service = OrderService(uow)
    orders = await service.get_org_orders(org_id)

    rows = []

    for o in orders:
        items = await uow.order_items.get_by_order(o.id)

        if not items:
            items = [None]

        for item in items:
            row = {
                "order_id": o.id,
                "client_id": o.client_id or "",
                "status": o.status,
                "total": o.total,
                "execution_date": o.execution_date,
                "notes": o.notes,
                "item_name": item.name if item else "",
                "item_price": item.price if item else "",
                "item_qty": item.qty if item else "",
            }
            add_custom_columns(row, o.local_fields)
            rows.append(row)

    try:
        ensure_export_limit(rows)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    headers = [
        "order_id",
        "client_id",
        "status",
        "total",
        "execution_date",
        "notes",
        "item_name",
        "item_price",
        "item_qty",
    ]
    custom_keys = sorted({k for r in rows for k in r if k.startswith("cf_")})
    csv_str = rows_to_csv(rows, headers + custom_keys)

    return Response(
        content=csv_str.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="orders.csv"'},
    )


router.include_router(csv_router)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = OrderService(uow)
    order = await service.get_order(order_id)

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
        )

    if str(order.org_id) != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    client_name = ""

    if order.client_id:
        from app.features.clients.repository import ClientRepository

        client = await ClientRepository(uow.session).get_by_id(order.client_id)

        if client:
            client_name = f"{client.name} {client.surname}"

    items = await service.get_items(order_id)

    return OrderResponse(
        id=order.id,
        org_id=order.org_id,
        client_id=order.client_id,
        client_name=client_name,
        status=order.status,
        total=float(order.total),
        execution_date=order.execution_date,
        notes=order.notes,
        photos=order.photos or [],
        local_fields=order.local_fields or {},
        custom_fields=order.custom_fields or {},
        is_deleted=order.is_deleted,
        items=[OrderItemResponse.model_validate(i) for i in items],
    )


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(
    order_id: UUID,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = OrderService(uow)
    order = await service.get_order(order_id)

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
        )

    if str(order.org_id) != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    await service.delete_order(order_id, updated_by=current_user.id)


@router.post(
    "/{order_id}/items",
    response_model=OrderItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_item(
    order_id: UUID,
    data: OrderItemCreate,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = OrderService(uow)
    item = await service.add_item(
        order_id=order_id,
        product_id=data.product_id,
        name=data.name,
        price=data.price,
        qty=data.qty,
        org_id=org_id,
    )

    return OrderItemResponse.model_validate(item)


@router.patch(
    "/{order_id}/items/{item_id}",
    response_model=OrderItemResponse,
)
async def update_item(
    order_id: UUID,
    item_id: UUID,
    data: OrderItemUpdate,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = OrderService(uow)
    item = await service.update_item(
        order_id=order_id,
        item_id=item_id,
        org_id=org_id,
        name=data.name,
        price=data.price,
        qty=data.qty,
    )

    return OrderItemResponse.model_validate(item)


@router.get("/{order_id}/items", response_model=list[OrderItemResponse])
async def list_items(
    order_id: UUID,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = OrderService(uow)
    items = await service.get_items(order_id, org_id=org_id)

    return [OrderItemResponse.model_validate(i) for i in items]


@router.delete("/{order_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(
    order_id: UUID,
    item_id: UUID,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = OrderService(uow)
    await service.remove_item(order_id=order_id, item_id=item_id, org_id=org_id)


@router.post(
    "/{order_id}/write-offs",
    response_model=WriteOffResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_writeoff(
    order_id: UUID,
    data: WriteOffItemCreate,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = OrderService(uow)
    wo = await service.write_off_for_order_item(
        org_id=org_id,
        order_id=order_id,
        order_item_id=data.order_item_id,
        qty=data.qty,
        reason=data.reason,
    )

    return WriteOffResponse.model_validate(wo)


@router.post("/{order_id}/status", response_model=OrderResponse)
async def change_status(
    order_id: UUID,
    data: StatusUpdate,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = OrderService(uow)
    order = await service.get_order(order_id)

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found"
        )

    if str(order.org_id) != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    updated_order = await service.change_status(
        order_id, data.status, updated_by=current_user.id
    )

    if updated_order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    client_name = ""

    if updated_order.client_id:
        from app.features.clients.repository import ClientRepository

        client = await ClientRepository(uow.session).get_by_id(updated_order.client_id)

        if client:
            client_name = f"{client.name} {client.surname}"

    items = await service.get_items(order_id)

    return OrderResponse(
        id=updated_order.id,
        org_id=updated_order.org_id,
        client_id=updated_order.client_id,
        client_name=client_name,
        status=updated_order.status,
        total=float(updated_order.total),
        execution_date=updated_order.execution_date,
        notes=updated_order.notes,
        photos=updated_order.photos or [],
        local_fields=updated_order.local_fields or {},
        custom_fields=updated_order.custom_fields or {},
        is_deleted=updated_order.is_deleted,
        items=[OrderItemResponse.model_validate(i) for i in items],
    )
