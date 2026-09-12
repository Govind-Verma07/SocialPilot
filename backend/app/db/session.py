"""
app/db/session.py
-----------------
Database engine, session factory, and FastAPI dependency for DB sessions.

Usage in endpoint:
    from app.db.session import get_db
    ...
    async def my_endpoint(db: Session = Depends(get_db)):
        ...
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.core.config import settings

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,        # verify connections before use
    pool_size=5,
    max_overflow=10,
    echo=(settings.APP_ENV == "development"),  # log SQL in dev only
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """Yield a database session and close it after the request."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
