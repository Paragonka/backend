from app.features.legal.models import UserConsent


async def _register(client, email="consent@test.com", **extra):
    payload = {
        "email": email,
        "password": "Password123",
        "full_name": "Consent User",
        "consent_to_processing": True,
    }
    payload.update(extra)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201
    return resp.json()


async def _consents(test_session_factory, consent_type=None):
    from sqlalchemy import select

    async with test_session_factory() as session:
        stmt = select(UserConsent)
        if consent_type is not None:
            stmt = stmt.where(UserConsent.consent_type == consent_type)
        return (await session.execute(stmt)).scalars().all()


class TestConsentAPI:
    async def test_consent_cookie_requires_auth(self, client):
        resp = await client.post("/api/v1/consent/cookie")
        assert resp.status_code == 401

    async def test_consent_policy_requires_auth(self, client):
        resp = await client.post("/api/v1/consent/policy")
        assert resp.status_code == 401

    async def test_cookie_consent_records_row(self, client, test_session_factory):
        user = await _register(client)
        resp = await client.post(
            "/api/v1/consent/cookie",
            headers={
                "Authorization": f"Bearer {user['access_token']}",
                "User-Agent": "pytest-agent/1.0",
            },
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

        # Registration already created a policy consent row, so the cookie
        # consent adds a second row; assert on the cookie row specifically.
        rows = await _consents(test_session_factory, consent_type="cookie")
        assert len(rows) == 1
        assert str(rows[0].user_id) == user["user"]["id"]
        assert rows[0].user_agent == "pytest-agent/1.0"

    async def test_policy_consent_records_row(self, client, test_session_factory):
        user = await _register(client, email="policy@test.com")
        resp = await client.post(
            "/api/v1/consent/policy",
            headers={"Authorization": f"Bearer {user['access_token']}"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

        # Registration already created a policy consent row; the explicit
        # consent endpoint call inserts a second one.
        rows = await _consents(test_session_factory, consent_type="policy")
        assert len(rows) == 2
        assert all(str(r.user_id) == user["user"]["id"] for r in rows)
        assert rows[0].consent_type == "policy"


class TestRegisterConsent:
    async def test_register_with_consent_creates_policy_consent(
        self, client, test_session_factory
    ):
        user = await _register(client, consent_to_processing=True)

        rows = await _consents(test_session_factory)
        assert len(rows) == 1
        assert str(rows[0].user_id) == user["user"]["id"]
        assert rows[0].consent_type == "policy"

    async def test_register_without_consent_is_rejected(self, client):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "noconsent@test.com",
                "password": "Password123",
                "full_name": "Consent User",
                "consent_to_processing": False,
            },
        )
        assert resp.status_code == 422


class TestNoEnforcement:
    async def test_write_works_without_separate_policy_consent(self, client):
        # Simplified policy: consent is given during registration, with no separate
        # write-method blocking - email notification is sent 14 days in advance.
        user = await _register(client)
        headers = {"Authorization": f"Bearer {user['access_token']}"}

        resp = await client.post("/api/v1/orgs", json={"name": "Org"}, headers=headers)
        assert resp.status_code == 201
