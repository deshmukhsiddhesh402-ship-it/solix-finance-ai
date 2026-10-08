"""
Database session management. Uses a connection pool suitable for FastAPI's
async request lifecycle (sync engine + dependency-injected session — simple
and battle-tested; move to async SQLAlchemy only if you hit real concurrency
limits, which is unlikely for this workload).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency: yields a DB session, always closed after the request."""
    db = SessionLocal()
    try:
        yield db
    except BaseException:
        # Ensure a failed request cannot return an invalid/aborted transaction
        # to the pool when a caller did not explicitly roll back.
        db.rollback()
        raise
    finally:
        db.close()
