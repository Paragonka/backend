class TestAuthRegister:
    async def test_register_success(self, client):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@test.com",
                "password": "Password123",
                "full_name": "New User",
                "consent_to_processing": True,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "new@test.com"
        assert data["user"]["full_name"] == "New User"

    async def test_register_duplicate_email(self, client):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "dup@test.com",
                "password": "Password123",
                "full_name": "First",
                "consent_to_processing": True,
            },
        )
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "dup@test.com",
                "password": "Password123",
                "full_name": "Second",
                "consent_to_processing": True,
            },
        )
        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]

    async def test_register_invalid_email(self, client):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "Password123",
                "full_name": "Test",
                "consent_to_processing": True,
            },
        )
        assert response.status_code == 422

    async def test_register_short_password(self, client):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@test.com",
                "password": "123",
                "full_name": "Test",
                "consent_to_processing": True,
            },
        )
        assert response.status_code == 422


class TestAuthLogin:
    async def test_login_success(self, client):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "login@test.com",
                "password": "Password123",
                "full_name": "Login User",
                "consent_to_processing": True,
            },
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "login@test.com", "password": "Password123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == "login@test.com"

    async def test_login_wrong_password(self, client):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrongpass@test.com",
                "password": "Password123",
                "full_name": "Test",
                "consent_to_processing": True,
            },
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "wrongpass@test.com", "password": "WrongPass123"},
        )
        assert response.status_code == 401

    async def test_login_wrong_email(self, client):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@test.com", "password": "Password123"},
        )
        assert response.status_code == 401

    async def test_login_invalid_email_format(self, client):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "bad", "password": "Password123"},
        )
        assert response.status_code == 422


class TestAuthPasswordChange:
    async def test_change_password_success(self, client):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "changepass@test.com",
                "password": "Password123",
                "full_name": "Test",
                "consent_to_processing": True,
            },
        )
        token = reg.json()["access_token"]

        response = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "Password123", "new_password": "NewPass123"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_change_password_wrong_current(self, client):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrongcurrent@test.com",
                "password": "Password123",
                "full_name": "Test",
                "consent_to_processing": True,
            },
        )
        token = reg.json()["access_token"]

        response = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "WrongPass", "new_password": "NewPass123"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    async def test_change_password_unauthorized(self, client):
        response = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "test", "new_password": "newpass"},
        )
        assert response.status_code == 401


class TestAuthCookies:
    async def test_register_sets_cookies(self, client):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "cookie-reg@test.com",
                "password": "Password123",
                "full_name": "Cookie Test",
                "consent_to_processing": True,
            },
        )
        assert response.status_code == 201
        set_cookie = response.headers.get("set-cookie", "")
        assert "access_token=" in set_cookie
        assert "refresh_token=" in set_cookie
        assert "HttpOnly" in set_cookie or "httponly" in set_cookie.lower()

    async def test_login_sets_cookies(self, client):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "cookie-login@test.com",
                "password": "Password123",
                "full_name": "Cookie Login",
                "consent_to_processing": True,
            },
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "cookie-login@test.com", "password": "Password123"},
        )
        assert response.status_code == 200
        set_cookie = response.headers.get("set-cookie", "")
        assert "access_token=" in set_cookie
        assert "refresh_token=" in set_cookie

    async def test_refresh_from_cookie(self, client):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "cookie-refresh@test.com",
                "password": "Password123",
                "full_name": "Cookie Refresh",
                "consent_to_processing": True,
            },
        )
        refresh_token = reg.json()["refresh_token"]

        response = await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_from_body_still_works(self, client):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "body-refresh@test.com",
                "password": "Password123",
                "full_name": "Body Refresh",
                "consent_to_processing": True,
            },
        )
        refresh_token = reg.json()["refresh_token"]

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    async def test_logout_clears_cookies(self, client):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "logout-test@test.com",
                "password": "Password123",
                "full_name": "Logout Test",
                "consent_to_processing": True,
            },
        )
        cookies = {
            "access_token": reg.json()["access_token"],
            "refresh_token": reg.json()["refresh_token"],
        }

        response = await client.post(
            "/api/v1/auth/logout",
            cookies=cookies,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        set_cookie = response.headers.get("set-cookie", "")
        assert "access_token=;" in set_cookie or "Max-Age=0" in set_cookie
        assert "refresh_token=;" in set_cookie or "Max-Age=0" in set_cookie


class TestAuthPasswordReset:
    async def test_forgot_password_existing_user(self, client):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "reset-existing@test.com",
                "password": "Password123",
                "full_name": "Reset User",
                "consent_to_processing": True,
            },
        )
        response = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "reset-existing@test.com"},
        )
        assert response.status_code == 200
        data = response.json()
        # Dev mode (SMTP not configured) — token returned in response
        assert "reset_token" in data
        assert "reset_url" in data

    async def test_forgot_password_unknown_user(self, client):
        response = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nobody@test.com"},
        )
        # Still 200 — no account enumeration
        assert response.status_code == 200
        assert "reset_token" not in response.json()

    async def test_forgot_password_invalid_email(self, client):
        response = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "not-an-email"},
        )
        assert response.status_code == 422

    async def test_reset_password_valid_token(self, client):
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "reset-valid@test.com",
                "password": "Password123",
                "full_name": "Reset Valid",
                "consent_to_processing": True,
            },
        )
        forgot = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "reset-valid@test.com"},
        )
        token = forgot.json()["reset_token"]

        response = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "BrandNewPass123"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_reset_password_invalid_token(self, client):
        response = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": "garbage-token", "password": "BrandNewPass123"},
        )
        assert response.status_code == 400

    async def test_reset_password_short_password(self, client):
        response = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": "garbage-token", "password": "123"},
        )
        assert response.status_code == 422

    async def test_full_reset_flow(self, client):
        """register → forgot-password → reset-password → login with new password"""
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "reset-full@test.com",
                "password": "OldPass123",
                "full_name": "Full Flow",
                "consent_to_processing": True,
            },
        )

        forgot = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "reset-full@test.com"},
        )
        token = forgot.json()["reset_token"]

        reset = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "NewPass456"},
        )
        assert reset.status_code == 200

        # Old password no longer works
        old = await client.post(
            "/api/v1/auth/login",
            json={"email": "reset-full@test.com", "password": "OldPass123"},
        )
        assert old.status_code == 401

        # New password works
        new = await client.post(
            "/api/v1/auth/login",
            json={"email": "reset-full@test.com", "password": "NewPass456"},
        )
        assert new.status_code == 200
