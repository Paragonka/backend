import asyncio
import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.features.auth.models import RefreshSession  # noqa: F401
from app.features.clients.models import Client  # noqa: F401
from app.features.eav.models import EavAttribute  # noqa: F401
from app.features.legal.models import LegalNotification, UserConsent  # noqa: F401
from app.features.orders.models import Order, OrderItem, WriteOff  # noqa: F401
from app.features.orgs.models import (  # noqa: F401
    Invite,
    Organization,
    OrganizationSetting,
    UserOrg,
)
from app.features.products.models import Product  # noqa: F401
from app.features.receipts.models import Receipt, ReceiptItem  # noqa: F401
from app.features.users.models import User  # noqa: F401
from app.shared.base_model import Base

config = context.config

# Load .env so DATABASE_URL works for local (non-Docker) alembic runs
load_dotenv()

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use DATABASE_URL from environment (Docker) if set, otherwise fall back to alembic.ini
db_url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))

if db_url is None:
    raise RuntimeError("DATABASE_URL is not set and no url in alembic.ini")

config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    url = config.get_main_option("sqlalchemy.url")

    if url is None:
        raise RuntimeError("sqlalchemy.url is not configured")

    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
