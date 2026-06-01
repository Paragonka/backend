# DEPRECATED - server-rendered HTML/HTMX routes kept only for backwards compatibility.
# The SPA + JSON API are the supported entry points; do not add features here.
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.shared.templates import templates

router = APIRouter(tags=["legal"])


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return templates.TemplateResponse(request, "features/legal/privacy.html")


@router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    return templates.TemplateResponse(request, "features/legal/terms.html")


@router.get("/cookie", response_class=HTMLResponse)
async def cookie_page(request: Request):
    return templates.TemplateResponse(request, "features/legal/cookie.html")
