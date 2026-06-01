from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

DATABASE_URL = settings.database_url.get_secret_value()

engine = create_async_engine(
    DATABASE_URL,
    echo=(settings.log_level.upper() == "DEBUG"),
    pool_size=settings.db_pool_size,
    pool_pre_ping=settings.db_pool_pre_ping,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, expire_on_commit=False, class_=AsyncSession, autoflush=False
)
