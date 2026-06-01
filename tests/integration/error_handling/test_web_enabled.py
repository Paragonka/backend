import importlib

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_web_enabled_false_returns_json_errors(monkeypatch):
    """When web_enabled=False, non-API routes return 404 JSON.

    Uses importlib.reload to recreate the app with web_enabled=False,
    then restores the original app instance to avoid test pollution.
    """
    import app.core.config
    import app.main

    original_app = app.main.app

    monkeypatch.setattr(app.core.config.settings, "web_enabled", False)

    importlib.reload(app.main)

    async with AsyncClient(
        transport=ASGITransport(app=app.main.app), base_url="http://test"
    ) as client:
        response = await client.get("/")
        assert response.status_code == 404
        assert "application/json" in response.headers["content-type"]

        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "OK"}

    # Restore the original app to avoid test pollution
    app.main.app = original_app
