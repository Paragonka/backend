"""Feature-flag contract.

When FEATURE_CSV=false, CSV routes are not registered → 404.
"""

import pytest

from app.core.config import settings

pytestmark = pytest.mark.skipif(
    settings.feature_csv, reason="CSV enabled — 404 contract does not apply"
)


class TestCsvDisabledApi:
    async def test_clients_export_csv_404(self, client):
        resp = await client.get("/api/v1/clients/export.csv")
        assert resp.status_code == 404

    async def test_clients_import_404(self, client):
        resp = await client.post(
            "/api/v1/clients/import",
            files={"file": ("c.csv", b"name\nX", "text/csv")},
        )
        assert resp.status_code == 404

    async def test_products_export_csv_404(self, client):
        resp = await client.get("/api/v1/products/export.csv")
        assert resp.status_code == 404

    async def test_products_import_404(self, client):
        resp = await client.post(
            "/api/v1/products/import",
            files={"file": ("p.csv", b"name\nX", "text/csv")},
        )
        assert resp.status_code == 404

    async def test_orders_export_csv_404(self, client):
        resp = await client.get("/api/v1/orders/export.csv")
        assert resp.status_code == 404

    async def test_receipts_export_csv_404(self, client):
        resp = await client.get("/api/v1/receipts/export.csv")
        assert resp.status_code == 404


class TestCsvDisabledWeb:
    async def test_clients_import_page_404(self, client):
        resp = await client.get("/app/some-org-id/clients/import")
        assert resp.status_code == 404

    async def test_products_import_page_404(self, client):
        resp = await client.get("/app/some-org-id/products/import")
        assert resp.status_code == 404
