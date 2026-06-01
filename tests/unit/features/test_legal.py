from pathlib import Path


def test_privacy_template_exists():
    assert Path("templates/features/legal/privacy.html").exists()


def test_terms_template_exists():
    assert Path("templates/features/legal/terms.html").exists()


def test_cookie_template_exists():
    assert Path("templates/features/legal/cookie.html").exists()


def test_privacy_template_has_content():
    content = Path("templates/features/legal/privacy.html").read_text()
    assert "Политика конфиденциальности" in content


def test_terms_template_has_content():
    content = Path("templates/features/legal/terms.html").read_text()
    assert "Условия использования" in content


def test_cookie_template_has_content():
    content = Path("templates/features/legal/cookie.html").read_text()
    assert "Политика использования cookie" in content


def test_register_template_has_consent_checkbox():
    content = Path("templates/features/auth/register.html").read_text()
    assert "consent" in content
    assert "checkbox" in content
    assert "условия использования" in content


def test_base_template_has_cookie_banner():
    content = Path("templates/base.html").read_text()
    assert "cookie-banner" in content
    assert "acceptCookies" in content


def test_user_consent_model_exists():
    from app.features.legal.models import UserConsent

    assert UserConsent.__tablename__ == "user_consents"


def test_legal_model_imported_in_env():
    content = Path("alembic/env.py").read_text()
    assert (
        "from app.features.legal.models import LegalNotification, UserConsent"
        in content
    )


def test_legal_router_registered_in_web_module():
    content = Path("app/web.py").read_text()
    assert (
        "from app.features.legal.web_router import router as legal_web_router"
        in content
    )
    assert "include_router" in content
    assert "legal_web_router" in content


def test_legal_api_router_registered_in_main_module():
    content = Path("app/main.py").read_text()
    assert (
        "from app.features.legal.api_router import router as legal_api_router"
        in content
    )
    assert "app.include_router(legal_api_router)" in content
