# DEPRECATED - server-rendered HTML/HTMX routes kept only for backwards compatibility.
# The SPA + JSON API are the supported entry points; do not add features here.
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette import status

from app.core.uow import AppUnitOfWork
from app.features.eav.service import EavAttributeService
from app.features.users.models import User
from app.shared.constants import EAV_FIELD_TYPE_STRING, ENTITY_TYPE_CLIENT, ENTITY_TYPES
from app.shared.dependencies import get_current_user, get_uow, verify_org_access
from app.shared.templates import templates

router = APIRouter(tags=["eav-web"])


@router.get("/{org_id}/eav", response_class=HTMLResponse)
async def eav_list_page(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    entity_code: str = ENTITY_TYPE_CLIENT,
):
    if entity_code not in ENTITY_TYPES:
        entity_code = ENTITY_TYPE_CLIENT

    service = EavAttributeService(uow)
    attributes = await service.get_by_entity_code(org_id, entity_code)

    return templates.TemplateResponse(
        request,
        "features/eav/list.html",
        {
            "org_id": org_id,
            "attributes": attributes,
            "entity_code": entity_code,
        },
    )


@router.post("/{org_id}/eav/create")
async def eav_create(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    form = await request.form()
    service = EavAttributeService(uow)
    await service.create_attribute(
        org_id=org_id,
        entity_code=str(form.get("entity_code", ENTITY_TYPE_CLIENT)),
        code=str(form.get("code", "")),
        name=str(form.get("name", "")),
        field_type=str(form.get("field_type", EAV_FIELD_TYPE_STRING)),
        is_required=form.get("is_required") == "on",
        default_value=str(form.get("default_value", "")),
    )

    return RedirectResponse(
        url=(
            f"/app/{org_id}/eav?entity_code="
            f"{form.get('entity_code', ENTITY_TYPE_CLIENT)}"
        ),
        status_code=302,
    )


@router.post("/{org_id}/eav/{attribute_id}/delete")
async def eav_delete(
    request: Request,
    attribute_id: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    form = await request.form()
    service = EavAttributeService(uow)
    deleted = await service.delete_attribute(attribute_id, org_id=org_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attribute not found"
        )

    return RedirectResponse(
        url=(
            f"/app/{org_id}/eav?entity_code="
            f"{form.get('entity_code', ENTITY_TYPE_CLIENT)}"
        ),
        status_code=302,
    )
