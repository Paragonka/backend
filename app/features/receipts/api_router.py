from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.uow import AppUnitOfWork
from app.features.receipts.schemas import (
    PaginatedReceipts,
    ReceiptCreate,
    ReceiptItemResponse,
    ReceiptResponse,
)
from app.features.receipts.service import ReceiptService
from app.features.users.models import User
from app.shared.dependencies import get_current_user, get_uow, verify_org_access
from app.shared.feature_flags import RequireFeatureCsv

router = APIRouter(prefix="/api/v1/receipts", tags=["receipts"])

# TODO: CSV export - enabled only when FEATURE_CSV=true.
csv_router = APIRouter(tags=["receipts"])


@router.post("", response_model=ReceiptResponse, status_code=status.HTTP_201_CREATED)
async def create_receipt(
    data: ReceiptCreate,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = ReceiptService(uow)

    try:
        receipt = await service.create_receipt(
            org_id=org_id,
            items_data=data.items,
            client_id=data.client_id,
            order_id=data.order_id,
            receipt_date=data.receipt_date,
            source=data.source,
            raw_data=data.raw_data,
            notes=data.notes,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e

    return ReceiptResponse.model_validate(receipt)


@router.get("", response_model=PaginatedReceipts)
async def list_receipts(
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    filter_date_from: str | None = Query(None, alias="filter[date_from]"),
    filter_date_to: str | None = Query(None, alias="filter[date_to]"),
    filter_source: str | None = Query(None, alias="filter[source]"),
    filter_client_id: str | None = Query(None, alias="filter[client_id]"),
):
    service = ReceiptService(uow)
    receipts, next_cursor = await service.get_filtered(
        org_id=org_id,
        cursor=cursor,
        limit=limit,
        date_from=filter_date_from,
        date_to=filter_date_to,
        source=filter_source,
        client_id=filter_client_id,
    )

    return PaginatedReceipts(
        data=[ReceiptResponse.model_validate(r) for r in receipts],
        next_cursor=next_cursor,
    )


@router.get("/all", response_model=list[ReceiptResponse])
async def list_all_receipts(
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = ReceiptService(uow)
    receipts = await service.get_org_receipts(org_id)

    return [ReceiptResponse.model_validate(r) for r in receipts]


@csv_router.get("/export.csv")
async def export_receipts_csv(
    require_csv: RequireFeatureCsv,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    from app.shared.csv_export import ensure_export_limit, rows_to_csv

    service = ReceiptService(uow)
    receipts = await service.get_org_receipts(org_id)
    rows = []

    for r in receipts:
        row = {
            "client_id": r.client_id or "",
            "order_id": r.order_id or "",
            "receipt_date": r.receipt_date,
            "total": r.total,
            "source": r.source or "",
            "notes": r.notes or "",
        }
        rows.append(row)

    try:
        ensure_export_limit(rows)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    headers = [
        "client_id",
        "order_id",
        "receipt_date",
        "total",
        "source",
        "notes",
    ]
    csv_str = rows_to_csv(rows, headers)

    return Response(
        content=csv_str.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="receipts.csv"'},
    )


router.include_router(csv_router)


@router.get("/{receipt_id}", response_model=ReceiptResponse)
async def get_receipt(
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

    return ReceiptResponse.model_validate(receipt)


@router.get("/{receipt_id}/items", response_model=list[ReceiptItemResponse])
async def list_receipt_items(
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

    return [ReceiptItemResponse.model_validate(i) for i in items]


@router.delete("/{receipt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_receipt(
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
