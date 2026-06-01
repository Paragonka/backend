from httpx import AsyncClient


class TestRefreshMiddleware:
    """Test transparent token refresh via middleware."""

    async def test_api_401_passthrough(self, client: AsyncClient):
        """API routes should return 401 JSON, not redirect."""
        resp = await client.get("/api/v1/clients?org_id=some-org")
        assert resp.status_code == 401
        assert resp.headers.get("content-type", "").startswith("application/json")

    async def test_web_redirects_to_login_when_no_tokens(self, client: AsyncClient):
        """Web route without any tokens should redirect to login."""
        resp = await client.get("/app/orgs/select", follow_redirects=False)
        assert resp.status_code in (302, 307)
        assert "/app/auth/login" in resp.headers.get("location", "")

    async def test_web_refreshes_with_valid_refresh_token(self, client: AsyncClient):
        """Web route with expired access but valid refresh should get new tokens."""
        # Create real user and session via API
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "web-refresh@test.com",
                "password": "Password123",
                "full_name": "Web Refresh",
                "consent_to_processing": True,
            },
        )
        assert reg.status_code == 201
        refresh = reg.json()["refresh_token"]

        cookies = {"access_token": "expired-junk", "refresh_token": refresh}

        resp = await client.get(
            "/app/orgs/select",
            cookies=cookies,
            follow_redirects=False,
        )

        assert resp.status_code in (302, 307)
        location = resp.headers.get("location", "")
        assert location.endswith("/app/orgs/select") or location.endswith(
            "/app/orgs/select/"
        )

        set_cookie = resp.headers.get("set-cookie", "")
        assert "access_token=" in set_cookie
        assert "refresh_token=" in set_cookie

    async def test_web_redirects_login_on_bad_refresh(self, client: AsyncClient):
        """Web route with invalid tokens should redirect to login and clear cookies."""
        cookies = {"access_token": "bad", "refresh_token": "bad"}

        resp = await client.get(
            "/app/orgs/select",
            cookies=cookies,
            follow_redirects=False,
        )

        assert resp.status_code in (302, 307)
        assert "/app/auth/login" in resp.headers.get("location", "")

    async def test_web_does_not_refresh_on_auth_pages(self, client: AsyncClient):
        """Auth pages should not be intercepted (avoid redirect loops)."""
        resp = await client.get("/app/auth/login", follow_redirects=False)
        assert resp.status_code == 200

    async def test_refresh_api_endpoint(self, client: AsyncClient):
        """POST /api/v1/auth/refresh with valid token.

        Returns new token pair (with rotation).
        """
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "refresh-test2@test.com",
                "password": "Password123",
                "full_name": "Test2",
                "consent_to_processing": True,
            },
        )
        assert reg.status_code == 201
        refresh = reg.json()["refresh_token"]

        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "refresh-test2@test.com"
        # new refresh should be different (rotation)
        assert data["refresh_token"] != refresh

    async def test_refresh_api_invalid_token(self, client: AsyncClient):
        """POST /api/v1/auth/refresh with invalid token returns 401."""
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "garbage"},
        )
        assert resp.status_code == 401


class TestRefreshAsAccessRejected:
    """Refresh token must not be usable as Bearer for API."""

    async def test_refresh_as_bearer_on_clients_returns_401(self, client: AsyncClient):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "refresh-as-access@test.com",
                "password": "Password123",
                "full_name": "Tester",
                "consent_to_processing": True,
            },
        )
        assert reg.status_code == 201
        data = reg.json()
        refresh = data["refresh_token"]
        # try to use refresh as access
        resp = await client.get(
            "/api/v1/clients",
            headers={"Authorization": f"Bearer {refresh}"},
            params={"org_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert resp.status_code == 401

    async def test_access_token_works(self, client: AsyncClient):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "access-works@test.com",
                "password": "Password123",
                "full_name": "Tester",
                "consent_to_processing": True,
            },
        )
        access = reg.json()["access_token"]
        # create org with access
        org = await client.post(
            "/api/v1/orgs",
            json={"name": "OrgAccess"},
            headers={"Authorization": f"Bearer {access}"},
        )
        assert org.status_code == 201

    async def test_reset_token_as_access_rejected(self, client: AsyncClient):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "reset-as-access@test.com",
                "password": "Password123",
                "full_name": "Tester",
                "consent_to_processing": True,
            },
        )
        forgot = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "reset-as-access@test.com"},
        )
        token = forgot.json().get("reset_token")
        assert token
        resp = await client.get(
            "/api/v1/orgs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401


class TestChangePasswordRevokes:
    async def test_change_password_revokes_old_access_and_refresh(
        self, client: AsyncClient
    ):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "chg-pw@test.com",
                "password": "Password123",
                "full_name": "Chg",
                "consent_to_processing": True,
            },
        )
        assert reg.status_code == 201
        old_access = reg.json()["access_token"]
        old_refresh = reg.json()["refresh_token"]

        # change password with old access
        resp = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "Password123", "new_password": "NewPass1234"},
            headers={"Authorization": f"Bearer {old_access}"},
        )
        assert resp.status_code == 200

        # old access should now be 401 (iat < updated_at)
        org_resp = await client.get(
            "/api/v1/orgs",
            headers={"Authorization": f"Bearer {old_access}"},
        )
        assert org_resp.status_code == 401

        # old refresh should be 401 (revoked)
        refresh_resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": old_refresh},
        )
        assert refresh_resp.status_code == 401

        # also via cookie
        refresh_cookie_resp = await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": old_refresh},
        )
        assert refresh_cookie_resp.status_code == 401

        # login with new password should work
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "chg-pw@test.com", "password": "NewPass1234"},
        )
        assert login.status_code == 200
        new_access = login.json()["access_token"]
        # new access should work
        org2 = await client.get(
            "/api/v1/orgs",
            headers={"Authorization": f"Bearer {new_access}"},
        )
        assert org2.status_code == 200

    async def test_reset_password_revokes_sessions(self, client: AsyncClient):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "reset-revoke@test.com",
                "password": "Password123",
                "full_name": "Reset",
                "consent_to_processing": True,
            },
        )
        forgot = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "reset-revoke@test.com"},
        )
        token = forgot.json()["reset_token"]
        # also get old refresh via login
        login_old = await client.post(
            "/api/v1/auth/login",
            json={"email": "reset-revoke@test.com", "password": "Password123"},
        )
        old_refresh = login_old.json()["refresh_token"]
        old_access = login_old.json()["access_token"]

        # reset
        reset = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "BrandNew123"},
        )
        assert reset.status_code == 200

        # old refresh revoked
        r = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": old_refresh}
        )
        assert r.status_code == 401
        # old access revoked via iat
        r2 = await client.get(
            "/api/v1/orgs", headers={"Authorization": f"Bearer {old_access}"}
        )
        assert r2.status_code == 401


class TestReuseDetection:
    async def test_reuse_rotated_refresh_revokes_all(
        self, client: AsyncClient, test_session_factory
    ):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "reuse@test.com",
                "password": "Password123",
                "full_name": "Reuse",
                "consent_to_processing": True,
            },
        )
        assert reg.status_code == 201
        refresh1 = reg.json()["refresh_token"]

        # first rotation: refresh1 -> refresh2
        r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh1})
        assert r2.status_code == 200
        refresh2 = r2.json()["refresh_token"]

        # second rotation with refresh2 -> refresh3 (to ensure first is revoked)
        r3 = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh2})
        assert r3.status_code == 200
        refresh3 = r3.json()["refresh_token"]

        # reuse of already-rotated refresh1 should trigger revoke_all and return 401.
        # Clear the httpx cookie jar first: the register/refresh responses set a
        # refresh_token cookie which would otherwise be picked over the JSON body.
        client.cookies.clear()
        reuse = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh1}
        )
        assert reuse.status_code == 401

        # after reuse detection, even the latest refresh3 should be invalid (all revoked)  # noqa: E501
        client.cookies.clear()
        reuse2 = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh3}
        )
        assert reuse2.status_code == 401
        client.cookies.clear()
        reuse3 = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh2}
        )
        assert reuse3.status_code == 401

        # also check DB: no active sessions
        # need user id - decode refresh1 payload
        from app.core.security import decode_refresh_token
        from app.core.uow import AppUnitOfWork
        from app.features.auth.service import AuthService

        payload = decode_refresh_token(refresh1)
        assert payload is not None
        user_id = payload["sub"]
        async with AppUnitOfWork(test_session_factory) as uow:
            svc = AuthService(uow)
            sessions = await svc.list_sessions(user_id)
            assert len(sessions) == 0

        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "reuse@test.com", "password": "Password123"},
        )
        assert login.status_code == 200

    async def test_logout_revokes_current_and_allows_other_session(
        self, client: AsyncClient
    ):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "logout-reuse@test.com",
                "password": "Password123",
                "full_name": "Logout",
                "consent_to_processing": True,
            },
        )
        refresh1 = reg.json()["refresh_token"]
        # login second time to create second session
        login2 = await client.post(
            "/api/v1/auth/login",
            json={"email": "logout-reuse@test.com", "password": "Password123"},
        )
        refresh2 = login2.json()["refresh_token"]
        assert refresh1 != refresh2

        # logout first session (clear cookie jar so the body token wins over cookie)
        client.cookies.clear()
        resp = await client.post(
            "/api/v1/auth/logout", json={"refresh_token": refresh1}
        )
        assert resp.status_code == 200
        # refresh1 should now be invalid
        client.cookies.clear()
        r = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh1})
        assert r.status_code == 401
        # refresh2 should still be valid (other device)
        client.cookies.clear()
        r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh2})
        assert r2.status_code == 200


class TestSessionsEndpoints:
    async def test_list_and_revoke_sessions(self, client: AsyncClient):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "sessions@test.com",
                "password": "Password123",
                "full_name": "Sess",
                "consent_to_processing": True,
            },
        )
        access1 = reg.json()["access_token"]
        # create second session via login
        login2 = await client.post(
            "/api/v1/auth/login",
            json={"email": "sessions@test.com", "password": "Password123"},
        )
        access2 = login2.json()["access_token"]
        # list sessions with access1
        lst = await client.get(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {access1}"},
        )
        assert lst.status_code == 200
        sessions = lst.json()
        assert len(sessions) >= 2
        # at least one has is_current false/true handling; if we send refresh cookie, one will be current  # noqa: E501
        # try with cookie
        refresh1 = reg.json()["refresh_token"]
        lst2 = await client.get(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {access1}"},
            cookies={"refresh_token": refresh1},
        )
        assert lst2.status_code == 200
        s2 = lst2.json()
        currents = [s for s in s2 if s["is_current"]]
        assert len(currents) == 1

        # delete one session
        sid_to_delete = sessions[0]["id"]
        del_resp = await client.delete(
            f"/api/v1/auth/sessions/{sid_to_delete}",
            headers={"Authorization": f"Bearer {access1}"},
        )
        assert del_resp.status_code == 200

        lst3 = await client.get(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {access1}"},
        )
        assert len(lst3.json()) == len(sessions) - 1

        # delete all
        del_all = await client.delete(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {access2}"},
        )
        assert del_all.status_code == 200
        lst4 = await client.get(
            "/api/v1/auth/sessions",
            headers={"Authorization": f"Bearer {access2}"},
        )
        assert lst4.status_code == 200
        assert len(lst4.json()) == 0

    async def test_delete_nonexistent_session_404(self, client: AsyncClient):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "sess404@test.com",
                "password": "Password123",
                "full_name": "S404",
                "consent_to_processing": True,
            },
        )
        access = reg.json()["access_token"]
        resp = await client.delete(
            "/api/v1/auth/sessions/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {access}"},
        )
        assert resp.status_code == 404

    async def test_sessions_require_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/sessions")
        assert resp.status_code == 401
        resp2 = await client.delete("/api/v1/auth/sessions")
        assert resp2.status_code == 401
