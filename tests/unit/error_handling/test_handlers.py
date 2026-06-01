from pathlib import Path


class TestErrorTemplates:
    def test_404_template_exists(self):
        assert Path("templates/errors/404.html").exists()

    def test_500_template_exists(self):
        assert Path("templates/errors/500.html").exists()

    def test_403_template_exists(self):
        assert Path("templates/errors/403.html").exists()

    def test_error_templates_contain_expected_text(self):
        content_404 = Path("templates/errors/404.html").read_text()
        content_500 = Path("templates/errors/500.html").read_text()
        content_403 = Path("templates/errors/403.html").read_text()
        assert "404" in content_404
        assert "500" in content_500
        assert "403" in content_403
        assert "Страница не найдена" in content_404 or "404" in content_404
        assert "Внутренняя ошибка" in content_500 or "500" in content_500
        assert "Доступ запрещён" in content_403 or "403" in content_403

    def test_main_has_exception_handlers(self):
        from app.main import app

        assert any("Exception" in str(k) for k in app.exception_handlers)

    def test_base_has_htmx_error_handling(self):
        content = Path("templates/base.html").read_text()
        assert "htmx:beforeSwap" in content
        assert "toast" in content
