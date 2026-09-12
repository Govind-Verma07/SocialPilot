"""phase_6_automated_publishing

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-09-12 03:30:00.000000

Phase 6 Schema:
  - Updates poststatus enum to include 'publishing'
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    # If running on PostgreSQL, update the enum with checkfirst/safely
    if conn.dialect.name == "postgresql":
        op.execute("ALTER TYPE poststatus ADD VALUE IF NOT EXISTS 'publishing'")


def downgrade() -> None:
    pass
