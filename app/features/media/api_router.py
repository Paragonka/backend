from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse

from app.core.uow import AppUnitOfWork
from app.features.media.service import MAX_FILE_SIZE, MediaService
from app.features.users.models import User
from app.shared.dependencies import get_current_user, get_uow, verify_org_access

router = APIRouter(prefix="/api/v1/media", tags=["media"])


@router.post("/upload/{entity_type}/{entity_id}", status_code=status.HTTP_200_OK)
async def upload_photo(
    entity_type: str,
    entity_id: str,
    file: UploadFile,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = MediaService(uow)
    # Bound the read so oversized uploads never hold more than the limit in
    # memory; the service rejects anything at/above the 10MB cap.
    file_bytes = await file.read(MAX_FILE_SIZE + 1)
    key = await service.add_photo_to_entity(
        org_id=org_id,
        entity_type=entity_type,
        entity_id=entity_id,
        file_bytes=file_bytes,
        content_type=file.content_type or "image/jpeg",
        filename=file.filename or "photo.jpg",
    )

    if not key:
        raise HTTPException(status_code=500, detail="Failed to upload file")

    return {"key": key}


@router.get("/list/{entity_type}/{entity_id}")
async def list_entity_photos(
    entity_type: str,
    entity_id: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    # Must be registered before the catch-all GET /{key:path} route below.
    service = MediaService(uow)
    keys = await service.get_entity_photos(
        org_id=org_id, entity_type=entity_type, entity_id=entity_id
    )

    return [{"key": key} for key in keys]


@router.get("/{key:path}")
async def get_media(
    key: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = MediaService(uow)
    url = await service.get_photo_url_in_org(key, org_id)

    return RedirectResponse(url=url, status_code=302)


@router.delete("/{key:path}")
async def delete_media(
    key: str,
    org_id: str = Depends(verify_org_access),
    uow: AppUnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    service = MediaService(uow)
    await service.remove_photo_by_key_in_org(key, org_id)

    return {"status": "ok"}
