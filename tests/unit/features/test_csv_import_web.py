from pathlib import Path


class TestCsvImportTemplates:
    def test_clients_import_template_exists(self):
        assert Path("templates/features/clients/import.html").exists()

    def test_products_import_template_exists(self):
        assert Path("templates/features/products/import.html").exists()

    def test_clients_list_has_import_link(self):
        content = Path("templates/features/clients/list.html").read_text()
        assert "import" in content.lower()

    def test_products_list_has_import_link(self):
        content = Path("templates/features/products/list.html").read_text()
        assert "import" in content.lower()

    def test_clients_web_router_has_import_route(self):
        from app.features.clients.web_router import csv_web_router

        routes = [getattr(r, "path", "") for r in csv_web_router.routes]
        assert any("import" in p for p in routes)

    def test_products_web_router_has_import_route(self):
        from app.features.products.web_router import csv_web_router

        routes = [getattr(r, "path", "") for r in csv_web_router.routes]
        assert any("import" in p for p in routes)
