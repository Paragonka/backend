from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.uow import AppUnitOfWork
from app.features.eav.schemas import (
    EavAttributeCreate,
    EavAttributeResponse,
    EavAttributeUpdate,
)
from app.features.eav.service import EavAttributeService
from app.features.users.models import User
from app.shared.dependencies import get_current_user, get_uow, verify_org_access

router = APIRouter(prefix="/api/v1/eav", tags=["eav"])


@router.post(
    "/attributes",
    response_model=EavAttributeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_attribute(
    data: EavAttributeCreate,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = EavAttributeService(uow)
    attr = await service.create_attribute(
        org_id=org_id,
        entity_code=data.entity_code,
        code=data.code,
        name=data.name,
        field_type=data.field_type,
        is_required=data.is_required,
        default_value=data.default_value,
    )

    return EavAttributeResponse.model_validate(attr)


@router.get("/attributes", response_model=list[EavAttributeResponse])
async def list_attributes(
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
    entity_code: str = "",
):
    service = EavAttributeService(uow)

    if entity_code:
        attrs = await service.get_by_entity_code(org_id, entity_code)
    else:
        attrs = await service.get_all(org_id)

    return [EavAttributeResponse.model_validate(a) for a in attrs]


@router.patch("/attributes/{attribute_id}", response_model=EavAttributeResponse)
async def update_attribute(
    attribute_id: UUID,
    data: EavAttributeUpdate,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = EavAttributeService(uow)
    attr = await service.update_attribute(
        attribute_id,
        org_id,
        name=data.name,
        field_type=data.field_type,
        is_required=data.is_required,
        default_value=data.default_value,
    )

    if not attr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attribute not found"
        )

    return EavAttributeResponse.model_validate(attr)


@router.delete("/attributes/{attribute_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attribute(
    attribute_id: UUID,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = EavAttributeService(uow)
    deleted = await service.delete_attribute(attribute_id, org_id=org_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attribute not found"
        )
