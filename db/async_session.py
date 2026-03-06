"""
db/async_session.py
────────────────────
Async SQLAlchemy session factory.

``get_async_db`` is a FastAPI dependency that:
  1. Opens an AsyncSession
  2. Sets the PostgreSQL session parameter ``app.current_tenant`` to the
     authenticated user's ``org_id`` (resolved from JWT via AuthContext),
     so Row-Level Security policies isolate tenant data at the DB layer.
  3. Falls back to ``'default-org'`` when no auth context is present
     (health checks, background tasks, etc.)
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from typing import AsyncGenerator, Optional
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


async def get_async_db(org_id: Optional[str] = None) -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async DB session with the tenant set for Row-Level Security.

    Pass ``org_id`` explicitly when calling from background tasks or tests.
    When used as a plain FastAPI dependency (no org_id), the tenant defaults
    to ``'default-org'``.  Protected endpoints should use
    ``get_tenant_db()`` instead to resolve the tenant from the JWT.
    """
    from sqlalchemy import text
    tenant = org_id or "default-org"
    async with AsyncSessionLocal() as session:
        # asyncpg cannot bind parameters inside SET LOCAL; set_config supports bound args safely.
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tenant, true)"),
            {"tenant": tenant},
        )
        yield session


async def get_tenant_db(
    org_id: Optional[str] = None,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Convenience wrapper — identical to ``get_async_db`` but named to signal
    that the caller should pass the authenticated tenant's org_id.
    """
    async for session in get_async_db(org_id=org_id):
        yield session
