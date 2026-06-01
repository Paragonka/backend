import uuid

from app.core.log import get_logger
from app.core.uow import AppUnitOfWork
from app.shared.exceptions import (
    MediaValidationError,
    NotFoundException,
)
from app.shared.s3 import s3_client

logger = get_logger(__name__)

_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024

_MAGIC_BYTES = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/webp": b"RIFF",
}

_EXT_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _validate_magic_bytes(file_bytes: bytes, content_type: str) -> None:
    expected = _MAGIC_BYTES.get(content_type)

    if expected is None:
        return

    if not file_bytes.startswith(expected):
        raise MediaValidationError(
            f"File content does not match declared type: {content_type}"
        )


class MediaService:
    def __init__(self, uow: AppUnitOfWork):
        self.uow = uow

    def _resolve_repo(self, entity_type: str):
        if entity_type == "clients":
            from app.features.clients.repository import ClientRepository

            return ClientRepository(self.uow.session)

        if entity_type == "products":
            from app.features.products.repository import ProductRepository

            return ProductRepository(self.uow.session)

        if entity_type == "orders":
            from app.features.orders.repository import OrderRepository

            return OrderRepository(self.uow.session)

        return None

    async def upload_photo(
        self,
        org_id: str,
        entity_type: str,
        entity_id: str,
        file_bytes: bytes,
        content_type: str,
        filename: str,
    ) -> str | None:
        if content_type not in _ALLOWED_TYPES:
            raise MediaValidationError(f"Unsupported content type: {content_type}")

        if len(file_bytes) == 0:
            raise MediaValidationError("File is empty")

        if len(file_bytes) > MAX_FILE_SIZE:
            raise MediaValidationError("File too large (max 10MB)")

        _validate_magic_bytes(file_bytes, content_type)
        ext = _EXT_MAP.get(content_type, ".jpg")
        key = f"{org_id}/{entity_type}/{entity_id}/{uuid.uuid4()}{ext}"
        ok = await s3_client.upload_file(file_bytes, key, content_type)

        if not ok:
            logger.warning(
                "media_upload_failed",
                org_id=org_id,
                entity_type=entity_type,
                entity_id=entity_id,
                content_type=content_type,
                size=len(file_bytes),
            )
            return None

        logger.info(
            "media_uploaded",
            org_id=org_id,
            entity_type=entity_type,
            entity_id=entity_id,
            key=key,
            content_type=content_type,
            size=len(file_bytes),
        )
        return key

    async def get_photo_url(self, key: str, expires: int = 300) -> str | None:
        return await s3_client.get_presigned_url(key, expires)

    async def get_photo_url_in_org(self, key: str, org_id: str) -> str:
        if not key.startswith(f"{org_id}/"):
            raise NotFoundException(f"Media not found: {key}")

        url = await self.get_photo_url(key)

        if not url:
            raise NotFoundException(f"Media not found: {key}")

        return url

    async def remove_photo_by_key_in_org(self, key: str, org_id: str) -> bool:
        if not key.startswith(f"{org_id}/"):
            raise NotFoundException(f"Media not found: {key}")

        parts = key.split("/")
        entity_type = parts[1] if len(parts) >= 3 else None
        entity_id = parts[2] if len(parts) >= 3 else None
        removed = await self.remove_photo_from_entity(
            org_id=org_id, entity_type=entity_type, entity_id=entity_id, key=key
        )

        if not removed:
            raise NotFoundException(f"Media not found: {key}")

        return True

    async def remove_photo_from_entity(
        self,
        org_id: str,
        entity_type: str | None,
        entity_id: str | None,
        key: str,
    ) -> bool:
        if not entity_type or not entity_id:
            return False

        async with self.uow:
            repo = self._resolve_repo(entity_type)

            if repo is None:
                return False

            entity = await repo.get_by_id_and_org(entity_id, org_id)

            if not entity:
                return False

            photos = list(entity.photos or [])

            if key not in photos:
                return False

            photos.remove(key)
            entity.photos = photos
            await s3_client.delete_file(key)
            await self.uow.session.flush()

            logger.info(
                "media_deleted",
                org_id=org_id,
                entity_type=entity_type,
                entity_id=entity_id,
                key=key,
            )

            return True

    async def get_entity_photos(
        self,
        org_id: str,
        entity_type: str,
        entity_id: str,
    ) -> list[str]:
        async with self.uow:
            repo = self._resolve_repo(entity_type)

            if repo is None:
                raise NotFoundException(f"Unknown entity type: {entity_type}")

            entity = await repo.get_by_id_and_org(entity_id, org_id)

            if not entity:
                raise NotFoundException(
                    f"{entity_type.capitalize()} not found: {entity_id}"
                )

            return list(entity.photos or [])

    async def add_photo_to_entity(
        self,
        org_id: str,
        entity_type: str,
        entity_id: str,
        file_bytes: bytes,
        content_type: str,
        filename: str,
    ) -> str | None:
        async with self.uow:
            repo = self._resolve_repo(entity_type)

            if repo is None:
                raise MediaValidationError(f"Unknown entity type: {entity_type}")

            entity = await repo.get_by_id_and_org(entity_id, org_id)

            if not entity:
                raise NotFoundException(
                    f"{entity_type.capitalize()} not found: {entity_id}"
                )

            photos = list(entity.photos or [])

            if len(photos) >= 5:
                raise MediaValidationError("Maximum 5 photos per entity")

            key = await self.upload_photo(
                org_id, entity_type, entity_id, file_bytes, content_type, filename
            )

            if not key:
                return None

            photos.append(key)
            entity.photos = photos
            await self.uow.session.flush()

        return key
