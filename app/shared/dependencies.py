from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import Cookie, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.log import bind_request_context
from app.core.security import decode_access_token
from app.core.uow import AppUnitOfWork
from app.features.users.models import User
from app.shared.exceptions import (
    NotAuthenticatedException,
    OrgAccessDenied,
    ValidationException,
)


async def get_uow() -> AsyncGenerator[AppUnitOfWork]:
    # Deliberately NOT entering the UoW context here: each service's
    # `async with self.uow` must be the outermost (committing) level, so the
    # COMMIT happens inside the handler BEFORE the response is sent.
    # Opening the context here pushed _depth to 1 and deferred commit to
    # dependency teardown (after response) - read-after-write races on
    # keep-alive connections (401 on request right after register/login).
    uow = AppUnitOfWork(AsyncSessionLocal)
    uow.open()  # session for read-only deps (get_current_user, verify_org_access)

    try:
        yield uow
    finally:
        # finally: teardown must run even when the request task is cancelled -
        # a skipped rollback leaves an "idle in transaction" backend that can
        # block TRUNCATE/DDL on the touched tables until the connection dies.
        await uow.aclose()  # no-op if a service block already committed and closed


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(  # noqa: C901
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    access_token: str | None = Cookie(None),
    uow: AppUnitOfWork = Depends(get_uow),
) -> User:
    token = None

    if credentials is not None:
        token = credentials.credentials
    elif access_token is not None:
        token = access_token

    if token is None:
        raise NotAuthenticatedException()

    payload = decode_access_token(token)

    if not payload:
        raise NotAuthenticatedException()

    user_id = payload.get("sub")

    if not user_id:
        raise NotAuthenticatedException()

    from app.features.users.repository import UserRepository

    repo = UserRepository(uow.session)
    user = await repo.get_by_id(user_id)

    if not user:
        raise NotAuthenticatedException()

    # Invalidate access tokens issued before last password change (via updated_at).
    # Access tokens contain iat; if iat < user.updated_at ->
    # password was changed after token issued.
    # NOTE: updated_at == created_at for freshly registered users (within ~1s).
    # Clock skew between DB (now()) and app (now()) can be ~0.06s, so a naive
    # `iat < updated_at - 0.1` check is fragile for rapid password-change
    # (login -> immediate reset) where the gap is ~0.15-0.25s. Instead we
    # distinguish "fresh user" (updated_at ~= created_at) from "password
    # changed" (updated_at >> created_at) and only invalidate in the latter.
    iat = payload.get("iat")

    if iat is not None and getattr(user, "updated_at", None) is not None:
        try:
            from datetime import UTC

            upd = user.updated_at

            if upd.tzinfo is None:
                upd = upd.replace(tzinfo=UTC)

            created = getattr(user, "created_at", None)

            if created is not None:
                if created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)

                # Fresh user: updated_at == created_at (same INSERT). Use 0.2s
                # threshold to allow for DB/app clock skew while still
                # catching rapid password changes (<1s after registration).
                if abs((upd - created).total_seconds()) < 0.2:
                    pass
                elif float(iat) < upd.timestamp():
                    raise NotAuthenticatedException()
            elif float(iat) < upd.timestamp():
                raise NotAuthenticatedException()
        except NotAuthenticatedException:
            raise
        except Exception:  # noqa: S110 -- intentional fail-open: a malformed iat does not break authentication
            pass

    # Bind the acting user so every downstream log line in this request is
    # attributable to them (audit trail). Never bind secrets/tokens.
    bind_request_context(user_id=str(user.id))

    return user


async def verify_org_access(
    org_id: str,
    user: User = Depends(get_current_user),
    uow: AppUnitOfWork = Depends(get_uow),
) -> str:
    try:
        UUID(org_id)
    except ValueError as e:
        raise ValidationException(f"Invalid organization ID format: {org_id}") from e

    from app.features.orgs.models import UserOrg

    result = await uow.session.execute(
        select(UserOrg).where(UserOrg.user_id == str(user.id), UserOrg.org_id == org_id)
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise OrgAccessDenied(org_id)

    # Bind the tenant so every downstream log line is scoped to the org
    # (multi-tenant audit trail). user_id is already bound by get_current_user.
    bind_request_context(org_id=org_id)

    return org_id


async def verify_org_owner(
    org_id: str,
    user: User = Depends(get_current_user),
    uow: AppUnitOfWork = Depends(get_uow),
) -> str:
    from app.features.orgs.models import ROLE_OWNER, Organization, UserOrg

    org_id = await verify_org_access(org_id, user=user, uow=uow)

    result = await uow.session.execute(
        select(UserOrg.role, Organization.owner_id)
        .join(Organization, Organization.id == UserOrg.org_id)
        .where(UserOrg.user_id == str(user.id), UserOrg.org_id == org_id)
    )
    membership = result.one_or_none()

    if not membership:
        raise OrgAccessDenied(org_id)

    role, organization_owner_id = membership

    # `role` was added after organizations already existed. Those legacy
    # memberships were initially backfilled as `member`, so the canonical
    # organization owner must remain an owner even before the data migration
    # has run (or if an old deployment skipped it).
    if role != ROLE_OWNER and str(organization_owner_id) != str(user.id):
        raise OrgAccessDenied(org_id)

    return org_id
