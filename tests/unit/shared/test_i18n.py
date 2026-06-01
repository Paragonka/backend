from app.shared.i18n import I18n


def test_gettext_ru():
    i = I18n(locales_dir="locales")
    assert i.gettext("Дашборд", "ru") == "Дашборд"
    assert i.gettext("Клиенты", "ru") == "Клиенты"


def test_gettext_en():
    i = I18n(locales_dir="locales")
    assert i.gettext("Дашборд", "en") == "Dashboard"
    assert i.gettext("Клиенты", "en") == "Clients"


def test_gettext_pl():
    i = I18n(locales_dir="locales")
    assert i.gettext("Дашборд", "pl") == "Panel"
    assert i.gettext("Заказы", "pl") == "Zamówienia"


def test_gettext_missing_key():
    i = I18n(locales_dir="locales")
    assert i.gettext("nonexistent_key", "ru") == "nonexistent_key"


def test_gettext_unsupported_lang():
    i = I18n(locales_dir="locales")
    assert i.gettext("Дашборд", "fr") == "Дашборд"


def test_supported_langs():
    i = I18n(locales_dir="locales")
    langs = i.supported_langs()
    assert "ru" in langs
    assert "en" in langs
    assert "pl" in langs


def test_lang_name():
    i = I18n(locales_dir="locales")
    assert i.lang_name("ru") == "Русский"
    assert i.lang_name("en") == "English"
    assert i.lang_name("pl") == "Polski"
    assert i.lang_name("fr") == "fr"
