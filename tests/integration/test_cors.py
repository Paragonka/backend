"""CORS — preflight and simple API requests."""

from httpx import AsyncClient

ALLOWED_ORIGIN = "http://localhost:5173"
FOREIGN_ORIGIN = "http://evil.example"


class TestCorsPreflight:
    """OPTIONS preflight must be answered before auth middleware.

    CORSMiddleware is outermost.
    """

    async def test_preflight_allowed_origin(self, client: AsyncClient):
        resp = await client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert resp.status_code == 200
        assert resp.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
        assert resp.headers["access-control-allow-credentials"] == "true"
        assert "POST" in resp.headers.get("access-control-allow-methods", "")
        assert "content-type" in resp.headers.get("access-control-allow-headers", "")

    async def test_preflight_foreign_origin_no_acao(self, client: AsyncClient):
        """A foreign Origin does not receive access-control-allow-origin.

        Note: Starlette adds static headers to the preflight response
        (allow-methods/max-age/credentials) even for a foreign Origin — the browser
        ignores them without ACAO, so the contract is specifically the absence of ACAO.
        """
        resp = await client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": FOREIGN_ORIGIN,
                "Access-Control-Request-Method": "POST",
            },
        )
        assert "access-control-allow-origin" not in resp.headers

    async def test_simple_request_allowed_origin_gets_acao(self, client: AsyncClient):
        """A real (non-preflight) request with an allowed Origin receives ACAO."""
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "cors@test.com", "password": "WrongPassword123"},
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert resp.status_code in (400, 401)
        assert resp.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
        assert resp.headers["access-control-allow-credentials"] == "true"
