import contextlib

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.core.uow import AppUnitOfWork
from app.features.auth.dependencies import get_uow
from app.features.auth.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.features.auth.service import AuthService
from app.features.orgs.schemas import AcceptInviteRequest, AcceptInviteResponse
from app.features.orgs.service import InviteService
from app.features.users.schemas import UserResponse
from app.shared.cookies import clear_auth_cookies, set_auth_cookies
from app.shared.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host

    return None


def _user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _build_token_content(user, access_token: str, refresh_token: str) -> dict:
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse(id=user.id, email=user.email, full_name=user.full_name),
    ).model_dump(mode="json")


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    uow: AppUnitOfWork = Depends(get_uow),
):
    service = AuthService(uow)
    ip = _client_ip(request)
    ua = _user_agent(request)

    # One UoW block: register and create_session inside the service become
    # nested (depth>0) - user+consent+refresh_session are atomic and
    # committed before the response.
    async with uow:
        user = await service.register(
            body.email,
            body.password.get_secret_value(),
            body.full_name,
            accept_policy=body.consent_to_processing,
        )
        access_token, refresh_token = await service.create_session(str(user.id), ip, ua)

    response = JSONResponse(
        content=_build_token_content(user, access_token, refresh_token),
        status_code=201,
    )
    set_auth_cookies(response, access_token, refresh_token)

    return response


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    uow: AppUnitOfWork = Depends(get_uow),
):
    service = AuthService(uow)
    user = await service.login(body.email, body.password.get_secret_value())

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    ip = _client_ip(request)
    ua = _user_agent(request)
    access_token, refresh_token = await service.create_session(str(user.id), ip, ua)

    response = JSONResponse(
        content=_build_token_content(user, access_token, refresh_token),
        status_code=200,
    )
    set_auth_cookies(response, access_token, refresh_token)

    return response


@router.post("/refresh")
async def refresh(request: Request, uow: AppUnitOfWork = Depends(get_uow)):
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        with contextlib.suppress(Exception):
            body = await request.json()
            refresh_token = body.get("refresh_token")

    if not refresh_token:
        auth = request.headers.get("authorization")

        if auth and auth.lower().startswith("bearer "):
            refresh_token = auth[7:].strip()

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    service = AuthService(uow)
    ip = _client_ip(request)
    ua = _user_agent(request)
    result = await service.refresh_tokens(refresh_token, ip, ua)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    user, new_access, new_refresh = result

    response = JSONResponse(
        content=_build_token_content(user, new_access, new_refresh),
        status_code=200,
    )
    set_auth_cookies(response, new_access, new_refresh)

    return response


@router.post("/logout")
async def logout(
    request: Request,
    uow: AppUnitOfWork = Depends(get_uow),
):
    refresh_token = request.cookies.get("refresh_token")

    if not refresh_token:
        with contextlib.suppress(Exception):
            body = await request.json()

            if isinstance(body, dict):
                refresh_token = body.get("refresh_token")

    if refresh_token:
        service = AuthService(uow)

        with contextlib.suppress(Exception):
            await service.logout(refresh_token)

    response = JSONResponse(content={"status": "ok"})
    clear_auth_cookies(response)

    return response


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest, uow: AppUnitOfWork = Depends(get_uow)
):
    service = AuthService(uow)
    result = await service.request_password_reset(request.email)

    # Always return 200 to prevent email enumeration
    response = {"detail": "If an account exists, a reset link has been sent."}
    response.update(result)

    return response


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest, uow: AppUnitOfWork = Depends(get_uow)
):
    service = AuthService(uow)
    ok = await service.reset_password(
        request.token, request.password.get_secret_value()
    )

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    return {"status": "ok"}


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    uow: AppUnitOfWork = Depends(get_uow),
):
    service = AuthService(uow)
    ok = await service.change_password(
        str(current_user.id),
        request.current_password.get_secret_value(),
        request.new_password.get_secret_value(),
    )

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to change password"
        )

    return {"status": "ok"}


# ---- Session management ----


@router.post("/invites/accept", response_model=AcceptInviteResponse)
async def accept_invite(
    body: AcceptInviteRequest,
    current_user=Depends(get_current_user),
    uow: AppUnitOfWork = Depends(get_uow),
):
    service = InviteService(uow)
    org, membership = await service.accept_invite(body.token, str(current_user.id))

    return AcceptInviteResponse(org_id=org.id, org_name=org.name, role=membership.role)


@router.get("/sessions")
async def list_sessions(
    request: Request,
    current_user=Depends(get_current_user),
    uow: AppUnitOfWork = Depends(get_uow),
):
    service = AuthService(uow)
    sessions = await service.list_sessions(str(current_user.id))
    # Determine current session via refresh cookie hash/sid
    current_hash = None
    current_sid = None
    refresh_cookie = request.cookies.get("refresh_token")

    if refresh_cookie:
        from app.core.security import decode_refresh_token, hash_token

        payload = decode_refresh_token(refresh_cookie)

        if payload:
            current_sid = payload.get("sid")

        try:
            current_hash = hash_token(refresh_cookie)
        except Exception:
            current_hash = None

    result = []

    for s in sessions:
        is_current = False

        if (current_hash and s.token_hash == current_hash) or (
            current_sid and str(s.id) == str(current_sid)
        ):
            is_current = True

        last_used = getattr(s, "last_used_at", None)
        result.append(
            {
                "id": str(s.id),
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                "last_used_at": last_used.isoformat() if last_used else None,
                "ip": s.ip,
                "user_agent": s.user_agent,
                "is_current": is_current,
            }
        )

    return result


@router.delete("/sessions")
async def delete_all_sessions(
    current_user=Depends(get_current_user),
    uow: AppUnitOfWork = Depends(get_uow),
):
    service = AuthService(uow)
    await service.revoke_all_sessions(str(current_user.id))

    return {"status": "ok"}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user=Depends(get_current_user),
    uow: AppUnitOfWork = Depends(get_uow),
):
    service = AuthService(uow)
    ok = await service.revoke_session_by_id(str(current_user.id), session_id)

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    return {"status": "ok"}
