# DEPRECATED - server-rendered HTML/HTMX routes kept only for backwards compatibility.
# The SPA + JSON API are the supported entry points; do not add features here.
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette import status

from app.core.uow import AppUnitOfWork
from app.features.clients.service import ClientService
from app.features.eav.service import EavAttributeService
from app.features.orders.service import OrderService
from app.features.users.models import User
from app.shared.constants import ENTITY_TYPE_CLIENT
from app.shared.dependencies import get_current_user, get_uow, verify_org_access
from app.shared.exceptions import AppHttpException
from app.shared.feature_flags import RequireFeatureCsv
from app.shared.templates import templates
from app.shared.web_forms import extract_local_fields, parse_eav_filters

router = APIRouter(tags=["clients-web"])

# CSV import UI - enabled only when FEATURE_CSV=true (see config.feature_csv)
csv_web_router = APIRouter(tags=["clients-web"])

FILTER_FIELDS = [
    {"name": "name", "label": "Имя", "type": "text", "placeholder": "Имя"},
    {"name": "surname", "label": "Фамилия", "type": "text", "placeholder": "Фамилия"},
    {"name": "phone", "label": "Телефон", "type": "text", "placeholder": "Телефон"},
]


@router.get("/{org_id}/clients", response_class=HTMLResponse)
async def clients_list_page(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    filter_name: str | None = Query(None, alias="filter[name]"),
    filter_surname: str | None = Query(None, alias="filter[surname]"),
    filter_phone: str | None = Query(None, alias="filter[phone]"),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    service = ClientService(uow)

    eav_filters_raw = parse_eav_filters(request.query_params)

    clients, next_cursor, _total = await service.get_filtered(
        org_id=org_id,
        cursor=cursor,
        limit=limit,
        name=filter_name,
        surname=filter_surname,
        phone=filter_phone,
        eav_filters=eav_filters_raw or None,
    )

    eav_attributes = await EavAttributeService(uow).get_by_entity_code(
        org_id, ENTITY_TYPE_CLIENT
    )

    current_filters = {
        "name": filter_name or "",
        "surname": filter_surname or "",
        "phone": filter_phone or "",
    }
    current_eav = eav_filters_raw

    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(
            request,
            "features/clients/_list_fragment.html",
            {"clients": clients, "org_id": org_id, "next_cursor": next_cursor},
        )

    return templates.TemplateResponse(
        request,
        "features/clients/list.html",
        {
            "clients": clients,
            "org_id": org_id,
            "filter_fields": FILTER_FIELDS,
            "current_filters": current_filters,
            "eav_attributes": eav_attributes,
            "current_eav": current_eav,
            "next_cursor": next_cursor,
        },
    )


@router.get("/{org_id}/clients/create", response_class=HTMLResponse)
async def clients_create_page(
    request: Request,
    org_id: str = Depends(verify_org_access),
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request,
        "features/clients/create.html",
        {"org_id": org_id},
    )


@csv_web_router.get("/{org_id}/clients/import", response_class=HTMLResponse)
async def clients_import_page(
    request: Request,
    require_csv: RequireFeatureCsv,
    org_id: str = Depends(verify_org_access),
    current_user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request,
        "features/clients/import.html",
        {"org_id": org_id},
    )


@csv_web_router.post("/{org_id}/clients/import", response_class=HTMLResponse)
async def clients_import_upload(
    request: Request,
    require_csv: RequireFeatureCsv,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    file: UploadFile = File(...),
):
    from app.shared.csv_import import CsvImportResult, parse_csv

    content = await file.read()
    result = CsvImportResult()

    if len(content) > 5 * 1024 * 1024:
        result.add_error(0, "Файл слишком большой (макс 5 MB)")

        return templates.TemplateResponse(
            request,
            "features/clients/import.html",
            {"org_id": org_id, "result": result, "filename": file.filename},
        )

    try:
        _, rows = parse_csv(content)
    except ValueError as e:
        result.add_error(0, str(e))

        return templates.TemplateResponse(
            request,
            "features/clients/import.html",
            {"org_id": org_id, "result": result, "filename": file.filename},
        )

    if len(rows) > 5000:
        result.add_error(0, "Максимум 5000 строк за один импорт")

        return templates.TemplateResponse(
            request,
            "features/clients/import.html",
            {"org_id": org_id, "result": result, "filename": file.filename},
        )

    service = ClientService(uow)

    for i, row in enumerate(rows, start=2):
        try:
            await service.create_client(
                org_id=org_id,
                name=str(row.get("name", "")),
                surname=str(row.get("surname", "")),
                phone=str(row.get("phone", "")),
                notes=str(row.get("notes", "")),
            )
            result.created += 1
        except AppHttpException as e:
            result.add_error(i, e.message)
        except (ValueError, TypeError, KeyError) as e:
            result.add_error(i, str(e))

    return templates.TemplateResponse(
        request,
        "features/clients/import.html",
        {"org_id": org_id, "result": result, "filename": file.filename},
    )


router.include_router(csv_web_router)


@router.get("/{org_id}/clients/{client_id}", response_class=HTMLResponse)
async def client_detail_page(
    request: Request,
    client_id: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = ClientService(uow)
    client = await service.get_client_in_org(client_id, org_id)

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )

    orders = await OrderService(uow).get_org_client_orders(org_id, client_id)

    return templates.TemplateResponse(
        request,
        "features/clients/detail.html",
        {"client": client, "org_id": org_id, "orders": orders},
    )


@router.post("/{org_id}/clients/create")
async def create_client(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    form = await request.form()
    service = ClientService(uow)
    await service.create_client(
        org_id=org_id,
        name=str(form.get("name", "")),
        surname=str(form.get("surname", "")),
        phone=str(form.get("phone", "")),
        notes=str(form.get("notes", "")),
        local_fields=extract_local_fields(form),
    )

    return RedirectResponse(url=f"/app/{org_id}/clients", status_code=302)


@router.get("/{org_id}/clients/{client_id}/edit", response_class=HTMLResponse)
async def clients_edit_page(
    request: Request,
    client_id: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = ClientService(uow)
    client = await service.get_client_in_org(client_id, org_id)

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )

    return templates.TemplateResponse(
        request,
        "features/clients/edit.html",
        {"client": client, "org_id": org_id, "local_fields": client.local_fields or {}},
    )


@router.get("/{org_id}/clients/{client_id}/edit-form", response_class=HTMLResponse)
async def clients_edit_form_fragment(
    request: Request,
    client_id: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = ClientService(uow)
    client = await service.get_client_in_org(client_id, org_id)

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )

    return templates.TemplateResponse(
        request,
        "features/clients/edit_form.html",
        {"client": client, "org_id": org_id, "local_fields": client.local_fields or {}},
    )


@router.post("/{org_id}/clients/{client_id}/edit")
async def update_client(
    request: Request,
    client_id: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    form = await request.form()
    service = ClientService(uow)
    client = await service.update_client_in_org(
        client_id,
        org_id,
        name=str(form.get("name", "")),
        surname=str(form.get("surname", "")),
        phone=str(form.get("phone", "")),
        notes=str(form.get("notes", "")),
        local_fields=extract_local_fields(form),
    )

    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
        )

    return RedirectResponse(url=f"/app/{org_id}/clients", status_code=302)


@router.post("/{org_id}/clients/{client_id}/delete")
async def delete_client(
    request: Request,
    client_id: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    # the web layer uses the same service-level archiving (soft-delete)
    # as REST DELETE /api/v1/clients/{id}. There is no hard deletion.
    service = ClientService(uow)
    await service.archive_client(client_id, org_id)

    return RedirectResponse(url=f"/app/{org_id}/clients", status_code=302)
