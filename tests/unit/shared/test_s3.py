from unittest.mock import patch

from app.shared.s3 import S3Client


class TestS3ClientDisabled:
    def test_disabled_upload_returns_false(self):
        with patch("app.shared.s3.settings") as mock_settings:
            mock_settings.s3_enabled = False
            client = S3Client()
            result = client.upload_file(b"test", "key", "image/jpeg")
            import asyncio

            result = asyncio.run(result)
            assert result is False

    def test_disabled_presigned_returns_none(self):
        with patch("app.shared.s3.settings") as mock_settings:
            mock_settings.s3_enabled = False
            client = S3Client()
            import asyncio

            result = asyncio.run(client.get_presigned_url("key"))
            assert result is None

    def test_disabled_delete_returns_false(self):
        with patch("app.shared.s3.settings") as mock_settings:
            mock_settings.s3_enabled = False
            client = S3Client()
            import asyncio

            result = asyncio.run(client.delete_file("key"))
            assert result is False
