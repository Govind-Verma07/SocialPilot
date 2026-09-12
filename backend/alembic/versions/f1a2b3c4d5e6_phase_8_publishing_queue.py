"""phase_8_publishing_queue

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
Create Date: 2026-09-12 04:30:00.000000

Phase 8 Schema:
  - Creates publishing_jobs table with per-platform queueing, retries, and backoff fields.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'publishing_jobs' not in tables:
        op.create_table(
            'publishing_jobs',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('post_id', sa.String(length=36), nullable=False),
            sa.Column('social_account_id', sa.String(length=36), nullable=False),
            sa.Column('status', sa.String(length=30), nullable=False, server_default='queued'),
            sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
            sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['social_account_id'], ['social_accounts.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('post_id', 'social_account_id', name='uq_post_social_account_job'),
        )
        op.create_index(op.f('ix_publishing_jobs_post_id'), 'publishing_jobs', ['post_id'], unique=False)
        op.create_index(op.f('ix_publishing_jobs_social_account_id'), 'publishing_jobs', ['social_account_id'], unique=False)
        op.create_index(op.f('ix_publishing_jobs_status'), 'publishing_jobs', ['status'], unique=False)
        op.create_index(op.f('ix_publishing_jobs_next_retry_at'), 'publishing_jobs', ['next_retry_at'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'publishing_jobs' in tables:
        op.drop_table('publishing_jobs')
