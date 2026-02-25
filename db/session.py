"""db/session.py — single engine, correct URI from settings"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from core.config import settings

engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        # Defaulting to 'default-org' for now to demonstrate RLS multi-tenancy in sync worker
        db.execute(text("SET LOCAL app.current_tenant = 'default-org'"))
        yield db
    finally:
        db.close()


def create_all_tables():
    from db.base import Base
    import models  # noqa — registers all models
    Base.metadata.create_all(bind=engine)
