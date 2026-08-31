"""
app/db/base.py
--------------
SQLAlchemy declarative base.

This module ONLY defines Base. It does NOT import models.
Model imports for Alembic discovery are done in app/db/base_all.py.

ORM models import Base from this module:
    from app.db.base import Base
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared metadata base for all ORM models."""
    pass
