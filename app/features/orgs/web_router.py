# DEPRECATED - server-rendered HTML/HTMX routes kept only for backwards compatibility.
# The SPA + JSON API are the supported entry points; do not add features here.
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.uow import AppUnitOfWork
from app.features.orgs.service import OrgService
from app.features.users.models import User
from app.shared.dependencies import (
    get_current_user,
    get_uow,
    verify_org_access,
    verify_org_owner,
)
from app.shared.templates import templates

router = APIRouter(tags=["orgs-web"])


@router.get("/orgs/select", response_class=HTMLResponse)
async def orgs_select_page(
    request: Request,
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = OrgService(uow)
    orgs = await service.get_user_orgs(str(current_user.id))

    return templates.TemplateResponse(
        request,
        "features/orgs/select.html",
        {"orgs": orgs, "show_sidebar": False},
    )


@router.post("/orgs/create")
async def create_org(
    request: Request,
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    form = await request.form()
    service = OrgService(uow)
    org = await service.create_org(
        name=str(form.get("name", "")),
        owner_id=str(current_user.id),
        timezone=str(form.get("timezone", "UTC")),
    )

    return RedirectResponse(url=f"/app/{org.id}/dashboard", status_code=302)


@router.get("/{org_id}/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
):
    service = OrgService(uow)
    data = await service.get_dashboard(org_id)

    return templates.TemplateResponse(request, "features/orgs/dashboard.html", data)


@router.get("/{org_id}/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
):
    service = OrgService(uow)
    org = await service.get_org(org_id)
    settings = await service.get_settings(org_id)

    return templates.TemplateResponse(
        request,
        "features/orgs/settings.html",
        {"org": org, "org_id": org_id, "settings": settings},
    )


@router.post("/{org_id}/settings/update")
async def update_settings(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
):
    form = await request.form()
    service = OrgService(uow)
    currency = str(form.get("currency", "PLN"))
    await service.update_settings(org_id, {"currency": currency})

    return templates.TemplateResponse(
        request,
        "features/orgs/_settings_message.html",
        {"org_id": org_id},
    )


@router.post("/{org_id}/settings/rename")
async def rename_org(
    request: Request,
    org_id: str = Depends(verify_org_owner),
    uow: AppUnitOfWork = Depends(get_uow),
):
    form = await request.form()
    name = str(form.get("name", "")).strip()
    service = OrgService(uow)

    if name:
        await service.update_org(org_id, name)

    return RedirectResponse(url=f"/app/{org_id}/settings", status_code=302)


@router.post("/{org_id}/settings/delete")
async def delete_org(
    request: Request,
    org_id: str = Depends(verify_org_owner),
    uow: AppUnitOfWork = Depends(get_uow),
):
    form = await request.form()
    typed_name = str(form.get("name", ""))
    service = OrgService(uow)
    org = await service.get_org(org_id)

    if org and typed_name == org.name:
        await service.delete_org(org_id)

        return RedirectResponse(url="/app/orgs/select", status_code=302)

    return RedirectResponse(
        url=f"/app/{org_id}/settings?delete_error=1", status_code=302
    )
