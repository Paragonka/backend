from pathlib import Path


def _app_route_paths(app) -> list[str]:
    # FastAPI >= 0.141 resolves included routers lazily (_IncludedRouter),
    # so expand them explicitly instead of reading app.routes directly.
    paths: list[str] = []
    for route in app.routes:
        if hasattr(route, "effective_route_contexts"):
            paths.extend(ctx.path for ctx in route.effective_route_contexts())
        else:
            paths.append(getattr(route, "path", ""))
    return paths


class TestEavWeb:
    def test_eav_web_router_exists(self):
        from app.features.eav.web_router import router

        routes = [getattr(r, "path", "") for r in router.routes]
        assert len(routes) >= 3
        assert any("eav" in p for p in routes)

    def test_eav_list_template_exists(self):
        assert Path("templates/features/eav/list.html").exists()

    def test_eav_registered_in_main(self):
        from app.main import app

        paths = _app_route_paths(app)
        assert any("eav" in p for p in paths)

    def test_local_fields_component_exists(self):
        assert Path("templates/components/local_fields.html").exists()

    def test_photos_component_exists(self):
        assert Path("templates/components/photos.html").exists()

    def test_client_forms_include_local_fields(self):
        create = Path("templates/features/clients/create.html").read_text()
        edit = Path("templates/features/clients/edit.html").read_text()
        edit_form = Path("templates/features/clients/edit_form.html").read_text()
        assert "local_fields" in create
        assert "local_fields" in edit
        assert "local_fields" in edit_form

    def test_product_forms_include_local_fields(self):
        create = Path("templates/features/products/create.html").read_text()
        edit = Path("templates/features/products/edit.html").read_text()
        edit_form = Path("templates/features/products/edit_form.html").read_text()
        assert "local_fields" in create
        assert "local_fields" in edit
        assert "local_fields" in edit_form

    def test_product_forms_include_photos(self):
        create = Path("templates/features/products/create.html").read_text()
        edit = Path("templates/features/products/edit.html").read_text()
        assert "photos" in create
        assert "photos" in edit

    def test_order_forms_include_local_fields(self):
        create = Path("templates/features/orders/create.html").read_text()
        assert "local_fields" in create
