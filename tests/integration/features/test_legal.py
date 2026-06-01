import pytest


@pytest.mark.asyncio
async def test_privacy_page(client):
    resp = await client.get("/privacy")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "Политика конфиденциальности" in resp.text or "Privacy" in resp.text


@pytest.mark.asyncio
async def test_terms_page(client):
    resp = await client.get("/terms")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "Условия использования" in resp.text or "Terms" in resp.text


@pytest.mark.asyncio
async def test_cookie_page(client):
    resp = await client.get("/cookie")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "cookie" in resp.text.lower()


@pytest.mark.asyncio
async def test_cookie_consent_api_requires_auth(client):
    resp = await client.post("/api/v1/consent/cookie")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_legal_pages_have_navbar(client):
    for path in ("/privacy", "/terms", "/cookie"):
        resp = await client.get(path)
        assert resp.status_code == 200
        assert "Paragonka" in resp.text
