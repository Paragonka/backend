import pytest

from app.core.config import settings

pytestmark = pytest.mark.skipif(
    not settings.feature_csv, reason="CSV disabled by feature-flag"
)


@pytest.mark.anyio
class TestCsvImportWeb:
    async def test_clients_import_page_requires_auth(self, client):
        response = await client.get("/app/some-org-id/clients/import")
        assert response.status_code in (401, 403, 302)

    async def test_products_import_page_requires_auth(self, client):
        response = await client.get("/app/some-org-id/products/import")
        assert response.status_code in (401, 403, 302)
