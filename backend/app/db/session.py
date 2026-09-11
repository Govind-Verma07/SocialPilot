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
import socket
from urllib.parse import urlparse
from typing import Generator

from app.core.config import settings


def _get_connect_args(db_url: str) -> dict:
    connect_args = {}
    if "postgresql" in db_url:
        connect_args["connect_timeout"] = 10
    elif "sqlite" in db_url:
        connect_args["check_same_thread"] = False
    return connect_args


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_get_connect_args(settings.DATABASE_URL),
    pool_pre_ping=True,        # verify connections before use
    pool_size=10,
    max_overflow=20,
    pool_recycle=300,          # recycle idle connections every 5 mins
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
