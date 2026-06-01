# DEPRECATED - server-rendered HTML/HTMX routes kept only for backwards compatibility.
# The SPA + JSON API are the supported entry points; do not add features here.
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.core.security import decode_access_token
from app.shared.templates import templates

router = APIRouter(tags=["home"])


@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    access_token = request.cookies.get("access_token")
    is_authenticated = bool(access_token and decode_access_token(access_token))

    return templates.TemplateResponse(
        request,
        "features/home/index.html",
        {"is_authenticated": is_authenticated, "show_sidebar": False},
    )
