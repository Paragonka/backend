import pytest


@pytest.mark.anyio
class TestErrorPages:
    async def test_web_404_returns_html(self, client):
        response = await client.get("/app/nonexistent-page")
        assert response.status_code == 404
        assert "text/html" in response.headers["content-type"]

    async def test_api_404_returns_json(self, client):
        response = await client.get("/api/v1/nonexistent")
        assert response.status_code == 404
        assert (
            response.headers["content-type"] == "application/json; charset=utf-8"
            or "application/json" in response.headers["content-type"]
        )

    async def test_health_still_works(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "OK"}
