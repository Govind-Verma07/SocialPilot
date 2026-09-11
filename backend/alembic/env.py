"""
alembic/env.py
--------------
Alembic migration environment — configured for SocialPilot.

Key setup:
  - DATABASE_URL is read from the same .env as the FastAPI app
    (via app.core.config.settings), so there's a single source of truth.
  - target_metadata is set to Base.metadata which discovers all ORM models
    registered in app.db.base (all models are imported there).
  - Both online (direct DB) and offline (SQL script) modes are supported.
"""

import sys
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ---------------------------------------------------------------------------
# Make the backend/app package importable from here
# ---------------------------------------------------------------------------
# alembic/ lives inside backend/ so we add backend/ to sys.path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---------------------------------------------------------------------------
# Load application settings and Base metadata
# ---------------------------------------------------------------------------
from app.core.config import settings  # noqa: E402
from app.db.base_all import Base  # noqa: E402 — imports Base + all models

# ---------------------------------------------------------------------------
# Alembic Config object — provides access to alembic.ini values
# ---------------------------------------------------------------------------
config = context.config

# Override sqlalchemy.url with our validated DATABASE_URL from settings
# so we never have to duplicate the connection string.
# Override sqlalchemy.url with our validated DATABASE_URL from settings
# so we never have to duplicate the connection string.
# NOTE: ConfigParser uses % for interpolation, so we must escape any
# literal % characters (e.g. %40 → %%40) before passing to set_main_option.
_db_url = settings.DATABASE_URL.replace("%", "%%")
config.set_main_option("sqlalchemy.url", _db_url)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# target_metadata lets Alembic diff our ORM models against the live schema
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline mode — emit SQL to stdout without a live DB connection
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode — run against a live database connection
# ---------------------------------------------------------------------------
def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Check if the DB has a stale/orphan revision that doesn't exist in versions/
        try:
            from sqlalchemy import text
            rev_row = connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
            if rev_row and rev_row[0] == '8d0eb72eda8f':
                # Reconcile stale revision with current head
                connection.execute(text("UPDATE alembic_version SET version_num = '9dd7efe62534'"))
                connection.commit()
        except Exception:
            pass

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
