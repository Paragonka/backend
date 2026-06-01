import pytest


@pytest.mark.asyncio
async def test_language_switcher_redirects(client):
    """GET /lang/en sets lang cookie and redirects."""
    resp = await client.get(
        "/lang/en", headers={"referer": "http://test/app/orgs/select"}
    )
    assert resp.status_code == 302
    assert resp.headers.get("location") == "http://test/app/orgs/select"
    cookies = resp.cookies
    assert "lang" in cookies
    assert cookies["lang"] == "en"


@pytest.mark.asyncio
async def test_language_switcher_invalid_lang(client):
    """GET /lang/xx redirects to / without setting cookie."""
    resp = await client.get("/lang/xx")
    assert resp.status_code == 302
    location = resp.headers.get("location")
    assert location in ("http://test/", "/")
    assert "lang" not in resp.cookies


@pytest.mark.asyncio
async def test_language_switcher_sets_all_langs(client):
    for lang in ("ru", "en", "pl"):
        resp = await client.get(f"/lang/{lang}")
        assert resp.status_code == 302
        assert resp.cookies["lang"] == lang


@pytest.mark.asyncio
async def test_home_page_has_lang_in_context(client):
    """Home page renders with a language switcher (check cookie detection)."""
    resp = await client.get("/", cookies={"lang": "en"})
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_language_cookie_en(client):
    """With lang=en cookie, English navbar text should appear."""
    resp = await client.get("/", cookies={"lang": "en"})
    assert resp.status_code == 200
    text = resp.text
    # The navbar has translated login/register buttons when not authenticated
    assert "Log in" in text
    assert "Register" in text


@pytest.mark.asyncio
async def test_language_cookie_pl(client):
    """With lang=pl cookie, Polish navbar text should appear."""
    resp = await client.get("/", cookies={"lang": "pl"})
    assert resp.status_code == 200
    text = resp.text
    assert "Zaloguj" in text
    assert "Rejestracja" in text


@pytest.mark.asyncio
async def test_accept_language_header(client):
    """Without lang cookie, Accept-Language header is used."""
    resp = await client.get("/", headers={"accept-language": "en-US,en;q=0.9"})
    assert resp.status_code == 200
    text = resp.text
    assert "Log in" in text


@pytest.mark.asyncio
async def test_default_language_is_polish(client):
    """Without any language hint, default is pl."""
    resp = await client.get("/")
    assert resp.status_code == 200
    text = resp.text
    assert "Zaloguj" in text
    assert "Rejestracja" in text
