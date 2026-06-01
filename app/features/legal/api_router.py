from fastapi import APIRouter, Depends, Request

from app.core.uow import AppUnitOfWork
from app.features.legal.service import TYPE_COOKIE, TYPE_POLICY, LegalService
from app.shared.dependencies import get_current_user, get_uow

router = APIRouter(prefix="/api/v1/consent", tags=["legal"])


def _client_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host

    return None


async def _record_consent(
    request: Request,
    consent_type: str,
    current_user,
    uow: AppUnitOfWork,
):
    service = LegalService(uow)
    await service.record_consent(
        user_id=str(current_user.id),
        consent_type=consent_type,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/cookie")
async def accept_cookie_consent(
    request: Request,
    current_user=Depends(get_current_user),
    uow: AppUnitOfWork = Depends(get_uow),
):
    await _record_consent(request, TYPE_COOKIE, current_user, uow)

    return {"status": "ok"}


@router.post("/policy")
async def accept_policy_consent(
    request: Request,
    current_user=Depends(get_current_user),
    uow: AppUnitOfWork = Depends(get_uow),
):
    await _record_consent(request, TYPE_POLICY, current_user, uow)

    return {"status": "ok"}
