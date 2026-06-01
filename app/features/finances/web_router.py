# DEPRECATED - server-rendered HTML/HTMX routes kept only for backwards compatibility.
# The SPA + JSON API are the supported entry points; do not add features here.
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from app.core.uow import AppUnitOfWork
from app.features.finances.service import FinancesService
from app.features.users.models import User
from app.shared.dependencies import get_current_user, get_uow, verify_org_access
from app.shared.templates import templates

router = APIRouter(tags=["finances-web"])


@router.get("/{org_id}/finances", response_class=HTMLResponse)
async def finances_dashboard(
    request: Request,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    months: int = Query(12, ge=1, le=60),
):
    service = FinancesService(uow)
    summary = await service.get_summary(org_id=org_id, months=months)

    return templates.TemplateResponse(
        request,
        "features/finances/dashboard.html",
        {"org_id": org_id, "summary": summary, "months": months},
    )
