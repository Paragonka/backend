import asyncio
import os
from collections.abc import AsyncGenerator
from urllib.parse import urlparse

import asyncpg
from asyncpg.exceptions import DeadlockDetectedError
import pytest_asyncio
import sqlalchemy.exc
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.refresh_middleware import set_session_factory
from app.core.uow import AppUnitOfWork

# Ensure RefreshSession table is known to Base before create_all
from app.features.auth.models import RefreshSession  # noqa: F401
from app.main import app
from app.shared.base_model import Base
from app.shared.dependencies import get_uow

_db_url = urlparse(settings.database_url.get_secret_value())
_db_user = _db_url.username
_db_password = _db_url.password or ""
_db_host = _db_url.hostname or "localhost"
_db_port = _db_url.port or 5432
_DB_PREFIX = "paragonka_test"
_ADMIN_DSN = (
    f"postgresql+asyncpg://{_db_user}:{_db_password}@{_db_host}:{_db_port}/postgres"
)
_BASE_DB_URL = f"postgresql+asyncpg://{_db_user}:{_db_password}@{_db_host}:{_db_port}"

worker_id = os.environ.get("PYTEST_XDIST_WORKER", "master")
_db_suffix = "" if worker_id == "master" else f"_{worker_id}"
TEST_DATABASE_URL = f"{_BASE_DB_URL}/{_DB_PREFIX}{_db_suffix}"

_TRUNCATE_STMT = text(
    "TRUNCATE TABLE "
    + ", ".join(sorted(t.name for t in Base.metadata.sorted_tables))
    + " RESTART IDENTITY CASCADE"
)


async def _ensure_database() -> None:
    """Create worker-specific database if it doesn't exist."""
    db_name = f"{_DB_PREFIX}{_db_suffix}"
    conn = await asyncpg.connect(
        host=_db_host,
        port=_db_port,
        user=_db_user,
        password=_db_password,
        database="postgres",
    )
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await conn.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    await _ensure_database()
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session_factory(test_engine):
    return async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False
    )


@pytest_asyncio.fixture(autouse=True)
async def cleanup_db(test_engine):
    async with test_engine.begin() as conn:
        # Defense-in-depth: a leaked "idle in transaction" backend (e.g. a
        # dependency teardown skipped on cancellation) holds ACCESS SHARE and
        # would block TRUNCATE forever. Terminate such backends first.
        await conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = current_database() AND state = 'idle in transaction' "
                "AND pid <> pg_backend_pid()"
            )
        )
        for attempt in range(3):
            try:
                await conn.execute(_TRUNCATE_STMT)
                break
            except (DeadlockDetectedError, sqlalchemy.exc.DBAPIError) as exc:
                msg = str(exc).lower()
                orig = getattr(exc, "orig", None)
                is_deadlock = (
                    isinstance(exc, DeadlockDetectedError)
                    or isinstance(orig, DeadlockDetectedError)
                    or (orig is not None and "deadlockdetectederror" in type(orig).__name__.lower())
                    or "deadlock detected" in msg
                )
                if not is_deadlock:
                    raise
                if attempt == 2:
                    # Fall back to per-table DELETE/TRUNCATE to avoid multi-table AccessExclusiveLock
                    for table in reversed(Base.metadata.sorted_tables):
                        try:
                            await conn.execute(text(f"DELETE FROM {table.name}"))
                        except Exception:
                            await conn.execute(text(f"TRUNCATE {table.name} CASCADE"))
                    # Reset identities after fallback
                    for table in Base.metadata.sorted_tables:
                        try:
                            await conn.execute(
                                text(
                                    f"ALTER SEQUENCE IF EXISTS {table.name}_id_seq RESTART WITH 1"
                                )
                            )
                        except Exception:
                            pass
                    break
                await asyncio.sleep(0.2)


@pytest_asyncio.fixture
async def client(test_session_factory) -> AsyncGenerator[AsyncClient]:
    async def override_get_uow() -> AsyncGenerator[AppUnitOfWork]:
        uow = AppUnitOfWork(test_session_factory)
        uow.open()
        try:
            yield uow
        finally:
            await uow.aclose()

    app.dependency_overrides[get_uow] = override_get_uow
    set_session_factory(test_session_factory)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    set_session_factory(None)
