"""db/session.py — single engine, correct URI from settings"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator, Optional
from core.config import settings

engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db(org_id: Optional[str] = None) -> Generator[Session, None, None]:
    """Yield a sync session with the RLS tenant set."""
    db = SessionLocal()
    tenant = org_id or "default-org"
    try:
        db.execute(
            text("SELECT set_config('app.current_tenant', :tenant, true)"),
            {"tenant": tenant},
        )
        yield db
    finally:
        db.close()


def create_all_tables():
    from db.base import Base
    import models  # noqa — registers all models
    Base.metadata.create_all(bind=engine)
