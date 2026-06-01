import asyncio
import os

import pytest

# Ensure web UI is enabled during tests (overrides .env)
os.environ.setdefault("WEB_ENABLED", "true")
# Enable the legacy SSR routers too: integration tests cover them (legal
# pages, i18n, receipts web views, refresh middleware). Production keeps
# the default off.
os.environ.setdefault("WEB_ROUTERS_ENABLED", "true")
# Development mode: forgot-password exposes reset_token for test convenience
os.environ.setdefault("ENVIRONMENT", "development")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
