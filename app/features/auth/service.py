from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from uuid_extensions import uuid7

from app.core.config import settings
from app.core.log import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    decode_reset_token,
    get_password_hash_async,
    hash_token,
    verify_password_async,
)
from app.core.uow import AppUnitOfWork
from app.features.auth.email import create_email_sender
from app.features.auth.models import RefreshSession
from app.features.users.models import User
from app.features.users.repository import UserRepository
from app.shared.exceptions import EmailAlreadyRegistered, ValidationException

logger = get_logger(__name__)


def normalize_email(email: str) -> str:
    """Normalize email for case-insensitive handling.

    The domain is always case-insensitive (RFC 1035). The local part is
    lowercased too because most consumer providers (Gmail, etc.) treat it
    case-insensitively and we want a single canonical account per address.
    """
    return email.strip().lower()


class AuthService:
    def __init__(self, uow: AppUnitOfWork, email_sender: Any | None = None):
        self.uow = uow
        self.email_sender = email_sender or create_email_sender()

    @property
    def _users(self) -> UserRepository:
        return UserRepository(self.uow.session)

    async def register(
        self, email: str, password: str, full_name: str, accept_policy: bool
    ) -> User:
        email = normalize_email(email)

        if not accept_policy:
            logger.info("auth_register_policy_declined", email=email)
            raise ValidationException("Policy consent is required at registration")

        async with self.uow:
            existing = await self._users.get_by_email(email)

            if existing:
                logger.warning("auth_register_email_exists", email=email)
                raise EmailAlreadyRegistered(email)

            password_hash = await get_password_hash_async(password)
            user = User(email=email, password_hash=password_hash, full_name=full_name)
            user = await self._users.add(user)
            from app.features.legal.models import UserConsent

            self.uow.session.add(
                UserConsent(user_id=str(user.id), consent_type="policy")
            )
            await self.uow.session.flush()

            logger.info("auth_register_success", user_id=str(user.id), email=email)

            return user

    async def login(self, email: str, password: str) -> User | None:
        email = normalize_email(email)

        async with self.uow:
            user = await self._users.get_by_email(email)

            if not user:
                logger.warning("auth_login_failed", email=email, reason="no_such_user")
                return None

            if not await verify_password_async(password, user.password_hash):
                logger.warning(
                    "auth_login_failed",
                    user_id=str(user.id),
                    email=email,
                    reason="bad_password",
                )
                return None

            logger.info("auth_login_success", user_id=str(user.id), email=email)

            return user

    async def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> bool:
        async with self.uow:
            user = await self._users.get_by_id(user_id)

            if not user:
                return False

            if not await verify_password_async(current_password, user.password_hash):
                logger.warning(
                    "auth_password_change_failed",
                    user_id=user_id,
                    reason="bad_current_password",
                )
                return False

            new_hash = await get_password_hash_async(new_password)
            user.password_hash = new_hash
            # Explicit Python timestamp avoids DB vs app clock skew and
            # ensures the gap after token iat is at least the hashing time
            # (otherwise rapid login->reset could have gap <0.1s and flake).
            user.updated_at = datetime.now(UTC)
            self.uow.session.add(user)
            # revoke all refresh sessions after password change
            await self.uow.refresh_sessions.revoke_all_for_user(user_id)

            logger.info("auth_password_changed", user_id=user_id)

            return True

    async def forgot_password(self, email: str) -> str | None:
        """Generate a password reset token. Returns None if user not found
        (never reveal whether an account exists)."""

        email = normalize_email(email)

        async with self.uow:
            user = await self._users.get_by_email(email)

            if not user:
                return None

            from app.core.security import create_reset_token

            return create_reset_token(str(user.id))

    async def request_password_reset(self, email: str) -> dict:
        token = await self.forgot_password(email)

        if not token:
            # No such user: do NOT reveal existence, but record the attempt
            # (rate-limiting / abuse monitoring). No email is sent.
            logger.info(
                "auth_password_reset_requested", email=email, token_issued=False
            )
            return {}

        reset_url = f"{settings.FRONTEND_URL}/auth/reset-password?token={token}"
        await self.email_sender.send_password_reset(email, reset_url)
        logger.info("auth_password_reset_requested", email=email, token_issued=True)

        # Development convenience (SMTP not configured): expose the token for
        # testing. Never in production - a leaked reset token is account takeover.
        if settings.environment == "development" and not settings.smtp_host:
            return {"reset_token": token, "reset_url": reset_url}

        return {}

    async def reset_password(self, token: str, new_password: str) -> bool:
        """Reset the password using a reset token. Returns True on success."""

        async with self.uow:
            payload = decode_reset_token(token)

            if not payload:
                logger.warning("auth_password_reset_failed", reason="invalid_token")
                return False

            user_id = payload.get("sub")

            if not user_id:
                logger.warning("auth_password_reset_failed", reason="invalid_token")
                return False

            user = await self._users.get_by_id(user_id)

            if not user:
                logger.warning("auth_password_reset_failed", reason="no_such_user")
                return False

            # One-time use: a token issued before the last password change
            # (user.updated_at is bumped onupdate) has already been used.
            iat = payload.get("iat")

            if iat is not None and user.updated_at is not None:
                updated_at = user.updated_at

                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=UTC)

                if iat < updated_at.timestamp():
                    logger.warning(
                        "auth_password_reset_failed", reason="token_already_used"
                    )
                    raise ValidationException("Reset link has already been used")

            user.password_hash = await get_password_hash_async(new_password)
            user.updated_at = datetime.now(UTC)
            self.uow.session.add(user)
            await self.uow.refresh_sessions.revoke_all_for_user(user_id)

            logger.info("auth_password_reset_completed", user_id=user_id)

            return True

    # --- Refresh session lifecycle ---

    async def create_session(
        self, user_id: str, ip: str | None = None, user_agent: str | None = None
    ) -> tuple[str, str]:
        """Create a new refresh session and return (access_token, refresh_token)."""

        async with self.uow:
            return await self._create_session_inner(user_id, ip, user_agent)

    async def _create_session_inner(
        self, user_id: str, ip: str | None, user_agent: str | None
    ) -> tuple[str, str]:
        sid = uuid7()
        refresh_token = create_refresh_token(str(user_id), str(sid))
        token_hash = hash_token(refresh_token)
        now = datetime.now(UTC)
        expires_at = now + timedelta(days=settings.refresh_token_expire_days)
        ua = user_agent[:255] if user_agent else None
        session = RefreshSession(
            id=sid,
            user_id=UUID(str(user_id)),
            token_hash=token_hash,
            expires_at=expires_at,
            ip=ip,
            user_agent=ua,
            last_used_at=now,
        )

        self.uow.session.add(session)
        await self.uow.session.flush()
        access_token = create_access_token(str(user_id))

        return access_token, refresh_token

    async def _resolve_session(
        self, token_hash: str, sid: str | None
    ) -> RefreshSession | None:
        """Find session by token hash, falling back to sid lookup."""
        repo = self.uow.refresh_sessions
        session = await repo.get_by_token_hash(token_hash)

        # Fallback by sid if hash lookup missed
        # (e.g., older tokens without hash collision)
        if not session and sid:
            try:
                session = await repo.get_by_id(sid)
            except Exception:
                session = None

        return session

    def _is_session_valid(
        self, session: RefreshSession, user_id: str, now: datetime
    ) -> bool:
        """Session belongs to the user and is not expired."""
        if str(session.user_id) != str(user_id):
            return False

        # Ensure expires_at is timezone-aware for comparison
        exp = session.expires_at

        if exp is not None:
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=UTC)

            if exp < now:
                return False

        return True

    async def _handle_reuse(self, user_id: str) -> None:
        """Revoke all sessions in a separate committed transaction.

        The outer UoW transaction is rolled back when the endpoint raises
        HTTPException(401), so a bare revoke here would be lost.
        """
        inner = AppUnitOfWork(self.uow.session_factory)

        async with inner:
            await inner.refresh_sessions.revoke_all_for_user(user_id)

    async def _rotate_session(
        self,
        session: RefreshSession,
        user_id: str,
        now: datetime,
        ip: str | None,
        user_agent: str | None,
    ) -> tuple[str, str] | None:
        """Atomically revoke the old session and issue a fresh token pair.

        Returns None when the revoke did not happen (rowcount 0): another
        request rotated this session concurrently. The caller treats that as
        token reuse.
        """
        rotated = await self.uow.refresh_sessions.revoke(session.id)

        if not rotated:
            return None

        new_sid = uuid7()
        new_refresh = create_refresh_token(str(user_id), str(new_sid))
        new_hash = hash_token(new_refresh)
        expires_at = now + timedelta(days=settings.refresh_token_expire_days)
        ua = user_agent[:255] if user_agent else None
        new_session = RefreshSession(
            id=new_sid,
            user_id=session.user_id,
            token_hash=new_hash,
            expires_at=expires_at,
            ip=ip,
            user_agent=ua,
            last_used_at=now,
        )
        self.uow.session.add(new_session)
        await self.uow.session.flush()

        return create_access_token(str(user_id)), new_refresh

    async def refresh_tokens(
        self,
        old_refresh_token: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, str, str] | None:
        """Validate old refresh token, rotate session.

        Returns (user, new_access, new_refresh) or None.

        Implements reuse-detection: if old token was already revoked,
        revoke all sessions for user.
        """
        payload = decode_refresh_token(old_refresh_token)

        if not payload:
            return None

        user_id = payload.get("sub")
        sid = payload.get("sid")

        if not user_id:
            return None

        token_hash = hash_token(old_refresh_token)

        async with self.uow:
            session = await self._resolve_session(token_hash, sid)

            if not session:
                return None

            now = datetime.now(UTC)

            if not self._is_session_valid(session, user_id, now):
                return None

            if session.revoked_at is not None:
                # Reuse detected: a revoked (already-used/logged-out) refresh
                # token is being presented again - a likely token-theft signal.
                logger.warning(
                    "auth_refresh_reuse_detected",
                    user_id=str(user_id),
                    session_id=str(session.id),
                )
                await self._handle_reuse(user_id)

                return None

            # Valid session - rotate. A None result means another request won
            # the concurrent rotate race; treat it as reuse.
            result = await self._rotate_session(session, user_id, now, ip, user_agent)

            if result is None:
                logger.warning(
                    "auth_refresh_concurrent_rotation",
                    user_id=str(user_id),
                    session_id=str(session.id),
                )
                await self._handle_reuse(user_id)

                return None

            new_access, new_refresh = result
            user = await self._users.get_by_id(str(user_id))

            if not user:
                return None

            return user, new_access, new_refresh

    async def revoke_session_by_token(self, token: str) -> bool:
        """Revoke single session identified by raw refresh token.

        Returns True if revoked.
        """
        payload = decode_refresh_token(token)

        if not payload:
            try:
                token_hash = hash_token(token)
            except Exception:
                return False

            async with self.uow:
                sess = await self.uow.refresh_sessions.get_by_token_hash(token_hash)

                if sess and sess.revoked_at is None:
                    return await self.uow.refresh_sessions.revoke(sess.id)

                return False

        token_hash = hash_token(token)

        async with self.uow:
            sess = await self.uow.refresh_sessions.get_by_token_hash(token_hash)

            if not sess:
                sid = payload.get("sid")

                if sid:
                    try:
                        sess = await self.uow.refresh_sessions.get_by_id(sid)
                    except Exception:
                        sess = None

            if not sess or sess.revoked_at is not None:
                return False

            return await self.uow.refresh_sessions.revoke(sess.id)

    async def logout(self, token: str) -> None:
        """Logout: physically remove the refresh session so a reused logged-out
        token is treated as unknown (401) rather than a rotation-reuse theft."""
        token_hash = hash_token(token)
        payload = decode_refresh_token(token)
        user_id = payload.get("sub") if payload else None

        async with self.uow:
            await self.uow.refresh_sessions.delete_by_token_hash(token_hash)

        logger.info("auth_logout", user_id=str(user_id) if user_id else None)

    async def revoke_all_sessions(self, user_id: str) -> None:
        async with self.uow:
            await self.uow.refresh_sessions.revoke_all_for_user(user_id)

        logger.info("auth_sessions_revoked_all", user_id=str(user_id))

    async def revoke_session_by_id(self, user_id: str, session_id: str) -> bool:
        async with self.uow:
            repo = self.uow.refresh_sessions
            sess = await repo.get_by_id(session_id)

            if not sess or str(sess.user_id) != str(user_id):
                return False

            if sess.revoked_at is not None:
                return False

            revoked = await repo.revoke(sess.id)

        logger.info(
            "auth_session_revoked",
            user_id=str(user_id),
            session_id=str(session_id),
        )

        return revoked

    async def list_sessions(self, user_id: str) -> list[RefreshSession]:
        async with self.uow:
            return await self.uow.refresh_sessions.list_active_for_user(user_id)
