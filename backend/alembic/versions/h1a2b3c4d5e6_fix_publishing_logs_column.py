"""fix_publishing_logs_action_to_event_type

Revision ID: h1a2b3c4d5e6
Revises: g1a2b3c4d5e6
Create Date: 2026-09-12 06:00:00.000000

Fix: The publishing_logs table was created with column 'action' (from an older
schema version applied before Phase 9 finalised the model). The SQLAlchemy model
and all service code expect 'event_type'. This migration renames 'action' ->
'event_type' so the DB matches the ORM.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h1a2b3c4d5e6'
down_revision: Union[str, None] = 'g1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Only rename if 'action' exists AND 'event_type' does NOT exist yet
    cols = {c['name'] for c in inspector.get_columns('publishing_logs')}
    if 'action' in cols and 'event_type' not in cols:
        op.alter_column(
            'publishing_logs',
            'action',
            new_column_name='event_type',
            existing_type=sa.String(50),
            nullable=False,
        )
    # If 'event_type' already exists (idempotent), do nothing


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    cols = {c['name'] for c in inspector.get_columns('publishing_logs')}
    if 'event_type' in cols and 'action' not in cols:
        op.alter_column(
            'publishing_logs',
            'event_type',
            new_column_name='action',
            existing_type=sa.String(50),
            nullable=False,
        )
