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
from app.features.clients.schemas import (
    ClientCreate,
    ClientResponse,
    ClientUpdate,
    PaginatedClients,
)
from app.features.clients.service import ClientService
from app.features.orders.schemas import OrderResponse
from app.features.orders.service import OrderService
from app.features.users.models import User
from app.shared.dependencies import get_current_user, get_uow, verify_org_access
from app.shared.exceptions import AppHttpException
from app.shared.feature_flags import RequireFeatureCsv

router = APIRouter(prefix="/api/v1/clients", tags=["clients"])

# TODO: CSV feature routes - enabled only when FEATURE_CSV=true.
csv_router = APIRouter(tags=["clients"])


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    data: ClientCreate,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = ClientService(uow)
    client = await service.create_client(
        org_id=org_id,
        name=data.name,
        surname=data.surname,
        phone=data.phone,
        notes=data.notes,
        custom_fields=data.custom_fields,
        local_fields=data.local_fields,
    )

    return ClientResponse.model_validate(client)


@router.get("", response_model=PaginatedClients)
async def list_clients(
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    sort: str | None = Query(None),
    include_archived: bool = Query(False),
    filter_name: str | None = Query(None, alias="filter[name]"),
    filter_surname: str | None = Query(None, alias="filter[surname]"),
    filter_phone: str | None = Query(None, alias="filter[phone]"),
):
    service = ClientService(uow)
    clients, next_cursor, total = await service.get_filtered(
        org_id=org_id,
        cursor=cursor,
        limit=limit,
        name=filter_name,
        surname=filter_surname,
        phone=filter_phone,
        sort=sort,
        include_archived=include_archived,
    )

    return PaginatedClients(
        data=[ClientResponse.model_validate(c) for c in clients],
        next_cursor=next_cursor,
        total=total,
    )


@router.get("/all", response_model=list[ClientResponse])
async def list_all_clients(
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    include_archived: bool = Query(False),
):
    service = ClientService(uow)
    clients = await service.get_org_clients(org_id, include_archived=include_archived)

    return [ClientResponse.model_validate(c) for c in clients]


@csv_router.get("/export.csv")
async def export_clients_csv(
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

    service = ClientService(uow)
    clients = await service.get_org_clients(org_id)
    rows = []

    for c in clients:
        row = {
            "name": c.name,
            "surname": c.surname,
            "phone": c.phone,
            "notes": c.notes,
        }
        add_custom_columns(row, c.custom_fields)
        rows.append(row)

    try:
        ensure_export_limit(rows)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    headers = ["name", "surname", "phone", "notes"]
    custom_keys = sorted({k for r in rows for k in r if k.startswith("cf_")})
    csv_str = rows_to_csv(rows, headers + custom_keys)

    return Response(
        content=csv_str.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="clients.csv"'},
    )


@csv_router.post("/import", status_code=status.HTTP_200_OK)
async def import_clients(
    require_csv: RequireFeatureCsv,
    file: UploadFile,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    mode: str = Query("create", pattern="^(create|upsert)$"),
):
    from app.shared.csv_import import (
        CLIENT_CSV_COLUMNS,
        CsvImportResult,
        parse_csv,
        validate_csv_columns,
    )

    content = await file.read()
    result = CsvImportResult()

    try:
        headers, rows = parse_csv(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    col_errors = validate_csv_columns(headers, CLIENT_CSV_COLUMNS, "client")

    if col_errors:
        raise HTTPException(status_code=400, detail="; ".join(col_errors))

    if len(rows) > 5000:
        raise HTTPException(status_code=400, detail="Maximum 5000 rows per import")

    service = ClientService(uow)

    for i, row in enumerate(rows, start=2):
        try:
            custom_fields = _parse_custom_fields(row)

            if mode == "upsert":
                _, status_out = await service.upsert_client(
                    org_id=org_id,
                    name=str(row.get("name", "")),
                    surname=str(row.get("surname", "")),
                    phone=str(row.get("phone", "")),
                    notes=str(row.get("notes", "")),
                    custom_fields=custom_fields,
                )

                if status_out == "created":
                    result.created += 1
                else:
                    result.updated += 1
            else:
                await service.create_client(
                    org_id=org_id,
                    name=str(row.get("name", "")),
                    surname=str(row.get("surname", "")),
                    phone=str(row.get("phone", "")),
                    notes=str(row.get("notes", "")),
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


@router.get("/{client_id}/orders", response_model=list[OrderResponse])
async def get_client_orders(
    client_id: UUID,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    client = await ClientService(uow).get_client_in_org(client_id, org_id)

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )

    return await OrderService(uow).get_client_orders(org_id, client_id)


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: UUID,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    include_archived: bool = Query(False),
):
    service = ClientService(uow)
    client = await service.get_client_visible(
        client_id, org_id, include_archived=include_archived
    )

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )

    return ClientResponse.model_validate(client)


@router.post("/{client_id}/restore", response_model=ClientResponse)
async def restore_client(
    client_id: UUID,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    """Clear the archive flag. Composite org scope: missing/foreign -> 404."""
    service = ClientService(uow)
    client = await service.restore_client(client_id, org_id)

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )

    return ClientResponse.model_validate(client)


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: UUID,
    data: ClientUpdate,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = ClientService(uow)
    client = await service.update_client_in_org(
        client_id, org_id, **data.model_dump(exclude_none=True)
    )

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )

    return ClientResponse.model_validate(client)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: UUID,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    """DELETE archives the client (soft-delete); there is no hard deletion.

    Idempotent: a repeated call for an already archived client -> 204.
    Orders are preserved.
    """
    service = ClientService(uow)
    client = await service.archive_client(client_id, org_id)

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )
