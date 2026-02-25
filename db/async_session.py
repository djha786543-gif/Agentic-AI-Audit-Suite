from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import AsyncGenerator
from core.config import settings

async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URI,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    from sqlalchemy import text
    async with AsyncSessionLocal() as session:
        # Defaulting to 'default-org' for now to demonstrate RLS multi-tenancy
        await session.execute(text("SET LOCAL app.current_tenant = 'default-org'"))
        yield session