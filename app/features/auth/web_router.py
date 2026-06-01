# DEPRECATED - server-rendered HTML/HTMX routes kept only for backwards compatibility.
# The SPA + JSON API are the supported entry points; do not add features here.
import contextlib

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import settings
from app.core.uow import AppUnitOfWork
from app.features.auth.service import AuthService
from app.shared.dependencies import get_uow
from app.shared.templates import templates

router = APIRouter(tags=["auth-web"])


def _cookie_kwargs() -> dict:
    return {
        "httponly": True,
        "samesite": "lax",
        "path": "/",
        "secure": settings.cookie_secure,
    }


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


@router.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(
        request, "features/auth/login.html", {"show_sidebar": False}
    )


@router.post("/auth/login")
async def login(
    request: Request,
    uow: AppUnitOfWork = Depends(get_uow),
):
    form = await request.form()
    email = str(form.get("email", ""))
    password = str(form.get("password", ""))

    service = AuthService(uow)
    user = await service.login(email, password)

    if not user:
        return templates.TemplateResponse(
            request,
            "features/auth/login.html",
            {"error": "Неверный email или пароль"},
            status_code=401,
        )

    ip = _client_ip(request)
    ua = _user_agent(request)
    access_token, refresh_token = await service.create_session(str(user.id), ip, ua)
    response = RedirectResponse(url="/app/orgs/select", status_code=302)
    kwargs = _cookie_kwargs()
    response.set_cookie(
        key="access_token", value=access_token, max_age=60 * 60, **kwargs
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=60 * 60 * 24 * 30,
        **kwargs,
    )

    return response


@router.get("/auth/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(
        request, "features/auth/register.html", {"show_sidebar": False}
    )


@router.post("/auth/register")
async def register(
    request: Request,
    uow: AppUnitOfWork = Depends(get_uow),
):
    form = await request.form()
    email = str(form.get("email", ""))
    password = str(form.get("password", ""))
    full_name = str(form.get("full_name", ""))

    if form.get("consent") != "on":
        return templates.TemplateResponse(
            request,
            "features/auth/register.html",
            {
                "error": (
                    "Необходимо принять условия использования и политику "
                    "конфиденциальности."
                )
            },
            status_code=400,
        )

    service = AuthService(uow)

    try:
        user = await service.register(email, password, full_name, accept_policy=True)
    except Exception as e:
        return templates.TemplateResponse(
            request,
            "features/auth/register.html",
            {"error": str(e)},
            status_code=400,
        )

    ip = _client_ip(request)
    ua = _user_agent(request)
    access_token, refresh_token = await service.create_session(str(user.id), ip, ua)
    response = RedirectResponse(url="/app/orgs/select", status_code=302)
    kwargs = _cookie_kwargs()
    response.set_cookie(
        key="access_token", value=access_token, max_age=60 * 60, **kwargs
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=60 * 60 * 24 * 30,
        **kwargs,
    )

    return response


@router.get("/auth/logout")
async def logout(request: Request, uow: AppUnitOfWork = Depends(get_uow)):
    refresh_token = request.cookies.get("refresh_token")

    if refresh_token:
        service = AuthService(uow)

        with contextlib.suppress(Exception):
            await service.revoke_session_by_token(refresh_token)

    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")

    return response


@router.get("/auth/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse(
        request, "features/auth/forgot_password.html", {"show_sidebar": False}
    )


@router.post("/auth/forgot-password")
async def forgot_password_submit(
    request: Request,
    uow: AppUnitOfWork = Depends(get_uow),
):
    form = await request.form()
    email = str(form.get("email", ""))
    service = AuthService(uow)
    await service.forgot_password(email)

    return templates.TemplateResponse(
        request,
        "features/auth/forgot_password_sent.html",
        {"show_sidebar": False, "email": email},
    )


@router.get("/auth/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = ""):
    if not token:
        return RedirectResponse(url="/app/auth/login", status_code=302)

    return templates.TemplateResponse(
        request,
        "features/auth/reset_password.html",
        {"show_sidebar": False, "token": token},
    )


@router.post("/auth/reset-password")
async def reset_password_submit(
    request: Request,
    uow: AppUnitOfWork = Depends(get_uow),
):
    form = await request.form()
    token = str(form.get("token", ""))
    password = str(form.get("password", ""))
    service = AuthService(uow)
    ok = await service.reset_password(token, password)

    if not ok:
        return templates.TemplateResponse(
            request,
            "features/auth/reset_password.html",
            {
                "show_sidebar": False,
                "token": token,
                "error": "Неверная или просроченная ссылка",
            },
            status_code=400,
        )

    return templates.TemplateResponse(
        request,
        "features/auth/reset_password_success.html",
        {"show_sidebar": False},
    )
