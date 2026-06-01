from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.features.auth.service import AuthService
from app.features.users.models import User
from app.shared.exceptions import EmailAlreadyRegistered, ValidationException

USER_ID = "06a2502b-6534-7779-8000-4ff242017bf0"


class TestAuthServiceRegister:
    async def test_register_creates_user(self, mock_session, mock_uow):
        mock_session.execute.return_value = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        with patch(
            "app.features.auth.service.get_password_hash_async",
            return_value="hashed-pass",
        ):
            service = AuthService(mock_uow)
            await service.register(
                "test@test.com", "Password123", "Test User", accept_policy=True
            )

        assert mock_session.add.call_count == 2
        assert mock_session.flush.await_count == 2
        mock_session.refresh.assert_awaited_once()

    async def test_register_duplicate_email_raises(self, mock_session, mock_uow):
        mock_session.execute.return_value = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = MagicMock()

        service = AuthService(mock_uow)
        with pytest.raises(EmailAlreadyRegistered):
            await service.register(
                "dup@test.com", "Password123", "Dup User", accept_policy=True
            )


class TestAuthServiceLogin:
    async def test_login_success(self, mock_session, mock_uow):
        user = MagicMock(spec=User)
        user.email = "test@test.com"
        user.password_hash = "hashed-pass"
        mock_session.execute.return_value = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = user

        with patch(
            "app.features.auth.service.verify_password_async", return_value=True
        ):
            service = AuthService(mock_uow)
            result = await service.login("test@test.com", "Password123")

        assert result is not None
        assert result.email == "test@test.com"

    async def test_login_wrong_email_returns_none(self, mock_session, mock_uow):
        mock_session.execute.return_value = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        service = AuthService(mock_uow)
        result = await service.login("unknown@test.com", "Password123")

        assert result is None

    async def test_login_wrong_password_returns_none(self, mock_session, mock_uow):
        user = MagicMock(spec=User)
        user.password_hash = "hashed-pass"
        mock_session.execute.return_value = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = user

        with patch(
            "app.features.auth.service.verify_password_async", return_value=False
        ):
            service = AuthService(mock_uow)
            result = await service.login("test@test.com", "wrong")

        assert result is None


class TestAuthServiceChangePassword:
    async def test_change_password_success(self, mock_session, mock_uow):
        user = MagicMock(spec=User)
        user.password_hash = "hashed-pass"
        user.updated_at = None
        mock_session.execute.return_value = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = user
        mock_uow.refresh_sessions = MagicMock()
        mock_uow.refresh_sessions.revoke_all_for_user = __import__(
            "unittest.mock", fromlist=["AsyncMock"]
        ).AsyncMock()

        with (
            patch("app.features.auth.service.verify_password_async", return_value=True),
            patch(
                "app.features.auth.service.get_password_hash_async",
                return_value="new-hash",
            ),
        ):
            service = AuthService(mock_uow)
            result = await service.change_password(USER_ID, "Password123", "NewPass123")

        assert result is True
        assert user.password_hash == "new-hash"

    async def test_change_password_wrong_current(self, mock_session, mock_uow):
        user = MagicMock(spec=User)
        user.password_hash = "hashed-pass"
        mock_session.execute.return_value = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = user

        with patch(
            "app.features.auth.service.verify_password_async", return_value=False
        ):
            service = AuthService(mock_uow)
            result = await service.change_password(USER_ID, "wrong", "NewPass123")

        assert result is False

    async def test_change_password_user_not_found(self, mock_session, mock_uow):
        mock_session.execute.return_value = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        service = AuthService(mock_uow)
        result = await service.change_password(USER_ID, "Password123", "NewPass123")

        assert result is False


class TestAuthServiceForgotPassword:
    async def test_forgot_password_user_exists(self, mock_session, mock_uow):
        mock_session.execute.return_value = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = MagicMock(
            spec=User
        )

        with patch("app.core.security.create_reset_token", return_value="reset-token"):
            service = AuthService(mock_uow)
            result = await service.forgot_password("test@test.com")

        assert result == "reset-token"

    async def test_forgot_password_user_not_found(self, mock_session, mock_uow):
        mock_session.execute.return_value = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        service = AuthService(mock_uow)
        result = await service.forgot_password("unknown@test.com")

        assert result is None


class TestAuthServiceResetPassword:
    async def test_reset_password_valid_token(self, mock_session, mock_uow):
        user = MagicMock(spec=User)
        user.password_hash = "hashed-pass"
        mock_session.execute.return_value = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = user
        mock_uow.refresh_sessions = MagicMock()
        mock_uow.refresh_sessions.revoke_all_for_user = __import__(
            "unittest.mock", fromlist=["AsyncMock"]
        ).AsyncMock()

        with (
            patch(
                "app.features.auth.service.decode_reset_token",
                return_value={"sub": USER_ID, "type": "reset"},
            ),
            patch(
                "app.features.auth.service.get_password_hash_async",
                return_value="new-hash",
            ),
        ):
            service = AuthService(mock_uow)
            result = await service.reset_password("valid-token", "NewPass123")

        assert result is True
        assert user.password_hash == "new-hash"

    async def test_reset_password_invalid_token(self, mock_session, mock_uow):
        mock_session.execute.return_value = MagicMock()

        with patch("app.features.auth.service.decode_reset_token", return_value=None):
            service = AuthService(mock_uow)
            result = await service.reset_password("bad-token", "NewPass123")

        assert result is False

    async def test_reset_password_expired_token(self, mock_session, mock_uow):
        mock_session.execute.return_value = MagicMock()

        # ExpiredSignatureError is caught by decode_token → None
        with patch("app.features.auth.service.decode_reset_token", return_value=None):
            service = AuthService(mock_uow)
            result = await service.reset_password("expired-token", "NewPass123")

        assert result is False

    async def test_reset_password_wrong_type(self, mock_session, mock_uow):
        mock_session.execute.return_value = MagicMock()

        with patch(
            "app.features.auth.service.decode_reset_token",
            return_value=None,
        ):
            service = AuthService(mock_uow)
            result = await service.reset_password("access-token", "NewPass123")

        assert result is False

    async def test_reset_password_user_not_found(self, mock_session, mock_uow):
        mock_session.execute.return_value = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None

        with patch(
            "app.features.auth.service.decode_reset_token",
            return_value={
                "sub": USER_ID,
                "type": "reset",
            },
        ):
            service = AuthService(mock_uow)
            result = await service.reset_password("valid-token", "NewPass123")

        assert result is False

    async def test_reset_password_reused_token_raises(self, mock_session, mock_uow):
        user = MagicMock(spec=User)
        user.updated_at = datetime(2026, 8, 28, tzinfo=UTC)
        mock_session.execute.return_value = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = user

        with patch(
            "app.features.auth.service.decode_reset_token",
            return_value={
                "sub": USER_ID,
                "type": "reset",
                "iat": datetime(2026, 8, 27, tzinfo=UTC).timestamp(),
            },
        ):
            service = AuthService(mock_uow)
            with pytest.raises(ValidationException, match="already been used"):
                await service.reset_password("used-token", "NewPass123")

    async def test_reset_password_naive_updated_at_treated_as_utc(
        self, mock_session, mock_uow
    ):
        user = MagicMock(spec=User)
        # naive updated_at must be interpreted as UTC
        user.updated_at = datetime(2026, 8, 28, 12, 0, 0)
        mock_session.execute.return_value = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = user

        with patch(
            "app.features.auth.service.decode_reset_token",
            return_value={
                "sub": USER_ID,
                "type": "reset",
                "iat": datetime(2026, 8, 28, 11, 0, 0, tzinfo=UTC).timestamp(),
            },
        ):
            service = AuthService(mock_uow)
            with pytest.raises(ValidationException, match="already been used"):
                await service.reset_password("used-token", "NewPass123")

    async def test_reset_password_fresh_token_succeeds(self, mock_session, mock_uow):
        user = MagicMock(spec=User)
        user.password_hash = "hashed-pass"
        user.updated_at = datetime(2026, 8, 27, tzinfo=UTC)
        mock_session.execute.return_value = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = user
        mock_uow.refresh_sessions = MagicMock()
        mock_uow.refresh_sessions.revoke_all_for_user = __import__(
            "unittest.mock", fromlist=["AsyncMock"]
        ).AsyncMock()

        with (
            patch(
                "app.features.auth.service.decode_reset_token",
                return_value={
                    "sub": USER_ID,
                    "type": "reset",
                    "iat": datetime(2026, 8, 28, tzinfo=UTC).timestamp(),
                },
            ),
            patch(
                "app.features.auth.service.get_password_hash_async",
                return_value="new-hash",
            ),
        ):
            service = AuthService(mock_uow)
            result = await service.reset_password("fresh-token", "NewPass123")

        assert result is True
        assert user.password_hash == "new-hash"
