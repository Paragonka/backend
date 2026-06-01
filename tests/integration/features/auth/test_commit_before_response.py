"""Regression tests for commit-before-response.

Bug: get_uow opened the UoW context itself (_depth=1 at handler entry), so a
service's `async with self.uow` was nested (_depth=2) and the COMMIT fired
only in dependency teardown — AFTER the response was sent. An immediate
follow-up request on a keep-alive connection read stale/uncommitted data
(401 NOT_AUTHENTICATED right after register/login/refresh/change-password).
"""

import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import User
from app.main import app


@pytest.fixture
def asgi_events(monkeypatch):
    """Record ('commit', ...) and ('response_sent', status) in global order.

    Patches AsyncSession.commit to log every commit made by the app during a
    raw ASGI round-trip, and marks the moment the final response body chunk
    is sent. The invariant under test: the request's COMMIT must be recorded
    BEFORE response_sent.
    """
    events: list[tuple] = []
    orig_commit = AsyncSession.commit

    async def spy_commit(self):
        await orig_commit(self)
        events.append(("commit", id(self)))

    monkeypatch.setattr(AsyncSession, "commit", spy_commit)
    return events


async def _call_asgi(method, path, json_body=None, headers=None, events=None):
    """Minimal raw ASGI call; records response_sent into events."""
    body = b""
    raw_headers = [(b"content-type", b"application/json")]
    if json_body is not None:
        body = json.dumps(json_body).encode()
        raw_headers.append((b"content-length", str(len(body)).encode()))
    for key, value in (headers or {}).items():
        raw_headers.append((key.lower().encode(), value.encode()))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "server": ("testserver", 80),
        "client": ("testclient", 50000),
        "headers": raw_headers,
    }
    status_box: dict = {}
    done = False

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        nonlocal done
        if message["type"] == "http.response.start":
            status_box["status"] = message["status"]
        elif (
            message["type"] == "http.response.body"
            and not message.get("more_body", False)
            and not done
        ):
            done = True
            if events is not None:
                events.append(("response_sent", status_box.get("status")))

    await app(scope, receive, send)
    return status_box.get("status")


def _commits_before_response(events) -> int:
    resp_idx = next(i for i, e in enumerate(events) if e[0] == "response_sent")
    return sum(1 for e in events[:resp_idx] if e[0] == "commit")


class TestCommitBeforeResponse:
    async def test_register_commits_before_response(self, client, asgi_events):
        """User row (+consent+refresh session) must be committed before the
        201 response leaves the server."""
        status = await _call_asgi(
            "POST",
            "/api/v1/auth/register",
            json_body={
                "email": "commitorder@test.com",
                "password": "Password123",
                "full_name": "Commit Order",
                "consent_to_processing": True,
            },
            events=asgi_events,
        )
        assert status == 201
        assert _commits_before_response(asgi_events) >= 1, (
            "COMMIT happened only in dependency teardown "
            f"(after response): {asgi_events}"
        )

    async def test_login_commits_before_response(self, client, asgi_events):
        reg_status = await _call_asgi(
            "POST",
            "/api/v1/auth/register",
            json_body={
                "email": "loginorder@test.com",
                "password": "Password123",
                "full_name": "Login Order",
                "consent_to_processing": True,
            },
            events=asgi_events,
        )
        assert reg_status == 201

        asgi_events.clear()
        login_status = await _call_asgi(
            "POST",
            "/api/v1/auth/login",
            json_body={"email": "loginorder@test.com", "password": "Password123"},
            events=asgi_events,
        )
        assert login_status == 200
        # create_session writes RefreshSession -> must commit before response
        assert _commits_before_response(asgi_events) >= 1, (
            f"login did not commit refresh session before response: {asgi_events}"
        )


class TestImmediateFollowUpAfterRegister:
    """N register->immediate authenticated GET cycles without any sleep.

    Under a real server (see scripts/check_register_race.py) this raced with
    teardown-commit; kept here as a fast wiring regression guard.
    """

    N = 10

    async def test_followup_requests_all_authorized(self, client):
        for i in range(self.N):
            resp = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"race{i}@test.com",
                    "password": "Password123",
                    "full_name": f"Race {i}",
                    "consent_to_processing": True,
                },
            )
            assert resp.status_code == 201, f"register #{i}: {resp.text}"
            token = resp.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            orgs = await client.get("/api/v1/orgs", headers=headers)
            assert orgs.status_code == 200, (
                f"immediate GET /orgs #{i} got {orgs.status_code}: "
                "(user row not committed when response arrived)"
            )
            sessions = await client.get("/api/v1/auth/sessions", headers=headers)
            assert sessions.status_code == 200, (
                f"immediate GET /auth/sessions #{i} got {sessions.status_code}"
                " (refresh session not committed)"
            )


class TestVisibleFromSeparateSession:
    async def test_user_visible_in_independent_db_session_after_register(
        self, client, test_session_factory
    ):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "visible@test.com",
                "password": "Password123",
                "full_name": "Visible User",
                "consent_to_processing": True,
            },
        )
        assert resp.status_code == 201

        factory = test_session_factory
        async with factory() as session:
            user = await session.scalar(
                select(User).where(User.email == "visible@test.com")
            )
            assert user is not None, (
                "user row invisible from independent DB session right after "
                "register returned 201"
            )
