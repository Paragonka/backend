from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.uow import AppUnitOfWork
from app.features.orgs.schemas import (
    InviteCreate,
    InviteCreatedResponse,
    InviteListItemResponse,
    MemberResponse,
    OrgCreate,
    OrgResponse,
    OrgSettingsResponse,
    OrgSettingsUpdate,
    OrgUpdate,
)
from app.features.orgs.service import InviteService, OrgService
from app.features.users.models import User
from app.shared.dependencies import (
    get_current_user,
    get_uow,
    verify_org_access,
    verify_org_owner,
)

router = APIRouter(prefix="/api/v1/orgs", tags=["orgs"])


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_org(
    data: OrgCreate,
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = OrgService(uow)
    org = await service.create_org(data.name, str(current_user.id), data.timezone)

    return OrgResponse.model_validate(org)


@router.get("", response_model=list[OrgResponse])
async def list_orgs(
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = OrgService(uow)
    orgs = await service.get_user_orgs(str(current_user.id))

    return [OrgResponse.model_validate(o) for o in orgs]


@router.get("/{org_id}", response_model=OrgResponse)
async def get_org(
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
):
    service = OrgService(uow)
    org = await service.get_org(org_id)

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )

    return OrgResponse.model_validate(org)


@router.patch("/{org_id}", response_model=OrgResponse)
async def update_org(
    data: OrgUpdate,
    org_id: str = Depends(verify_org_owner),
    uow: AppUnitOfWork = Depends(get_uow),
):
    service = OrgService(uow)
    org = await service.update_org(org_id, data.name)

    return OrgResponse.model_validate(org)


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org(
    org_id: str = Depends(verify_org_owner),
    uow: AppUnitOfWork = Depends(get_uow),
):
    service = OrgService(uow)
    await service.delete_org(org_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{org_id}/settings", response_model=OrgSettingsResponse)
async def get_org_settings(
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
):
    service = OrgService(uow)
    settings = await service.get_settings(org_id)

    return OrgSettingsResponse(**settings)


@router.put("/{org_id}/settings", response_model=OrgSettingsResponse)
async def update_org_settings(
    data: OrgSettingsUpdate,
    org_id: str = Depends(verify_org_owner),
    uow: AppUnitOfWork = Depends(get_uow),
):
    service = OrgService(uow)
    settings = await service.update_settings(org_id, data.model_dump())

    return OrgSettingsResponse(**settings)


# ---- Members ----


@router.get("/{org_id}/members", response_model=list[MemberResponse])
async def list_members(
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
):
    service = OrgService(uow)
    members = await service.list_members(org_id)

    return [MemberResponse(**m) for m in members]


@router.delete("/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    user_id: str,
    org_id: str = Depends(verify_org_owner),
    current_user: User = Depends(get_current_user),
    uow: AppUnitOfWork = Depends(get_uow),
):
    service = OrgService(uow)
    await service.remove_member(org_id, user_id, str(current_user.id))

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- Invites (owner-only management) ----


@router.post(
    "/{org_id}/invites",
    response_model=InviteCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invite(
    data: InviteCreate,
    org_id: str = Depends(verify_org_owner),
    current_user: User = Depends(get_current_user),
    uow: AppUnitOfWork = Depends(get_uow),
):
    service = InviteService(uow)
    invite = await service.create_invite(org_id, data.email, str(current_user.id))

    return InviteCreatedResponse(
        invite_id=invite.id, token=invite.token, expires_at=invite.expires_at
    )


@router.get("/{org_id}/invites", response_model=list[InviteListItemResponse])
async def list_invites(
    org_id: str = Depends(verify_org_owner),
    uow: AppUnitOfWork = Depends(get_uow),
):
    service = InviteService(uow)
    invites = await service.list_active_invites(org_id)

    return [
        InviteListItemResponse(
            invite_id=i.id, email=i.email, token=i.token, expires_at=i.expires_at
        )
        for i in invites
    ]


@router.delete("/{org_id}/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invite(
    invite_id: str,
    org_id: str = Depends(verify_org_owner),
    uow: AppUnitOfWork = Depends(get_uow),
):
    service = InviteService(uow)
    revoked = await service.revoke_invite(invite_id, org_id)

    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found"
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
