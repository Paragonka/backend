import importlib
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Client:
    def __init__(self):
        self._client: Any | None = None
        self._boto3: Any = None
        self._enabled = False
        self._available = False

        try:
            self._boto3 = importlib.import_module("boto3")
            self._available = True
        except ImportError:
            logger.warning("boto3 not installed, S3 support disabled")

        if self._available and settings.s3_enabled:
            self._enabled = True
            self._client = self._boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key.get_secret_value()
                if settings.s3_secret_key
                else None,
                region_name=settings.s3_region or "us-east-1",
            )

    async def upload_file(self, file_bytes: bytes, key: str, content_type: str) -> bool:
        if not self._enabled or not self._client:
            logger.warning("S3 not configured, skipping upload of %s", key)

            return False

        import asyncio

        await asyncio.to_thread(
            self._client.put_object,
            Bucket=settings.s3_bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )

        return True

    async def get_presigned_url(self, key: str, expires: int = 300) -> str | None:
        if not self._enabled or not self._client:
            logger.warning("S3 not configured, skipping presigned url for %s", key)

            return None

        import asyncio

        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": key},
            ExpiresIn=expires,
        )

    async def delete_file(self, key: str) -> bool:
        if not self._enabled or not self._client:
            logger.warning("S3 not configured, skipping delete of %s", key)

            return False

        import asyncio

        await asyncio.to_thread(
            self._client.delete_object,
            Bucket=settings.s3_bucket,
            Key=key,
        )

        return True


s3_client = S3Client()
