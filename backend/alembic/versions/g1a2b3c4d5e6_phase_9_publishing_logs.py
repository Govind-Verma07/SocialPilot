"""phase_9_publishing_logs

Revision ID: g1a2b3c4d5e6
Revises: f1a2b3c4d5e6
Create Date: 2026-09-12 04:45:00.000000

Phase 9 Schema:
  - Creates publishing_logs table for publishing history, events, attempts, and audit tracking.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g1a2b3c4d5e6'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'publishing_logs' not in tables:
        op.create_table(
            'publishing_logs',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('post_id', sa.String(length=36), nullable=False),
            sa.Column('publishing_job_id', sa.String(length=36), nullable=True),
            sa.Column('social_account_id', sa.String(length=36), nullable=True),
            sa.Column('platform', sa.String(length=30), nullable=False),
            sa.Column('event_type', sa.String(length=50), nullable=False),
            sa.Column('status', sa.String(length=30), nullable=False),
            sa.Column('attempt_number', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('platform_post_id', sa.String(length=255), nullable=True),
            sa.Column('published_url', sa.Text(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['publishing_job_id'], ['publishing_jobs.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['social_account_id'], ['social_accounts.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_publishing_logs_post_id'), 'publishing_logs', ['post_id'], unique=False)
        op.create_index(op.f('ix_publishing_logs_publishing_job_id'), 'publishing_logs', ['publishing_job_id'], unique=False)
        op.create_index(op.f('ix_publishing_logs_platform'), 'publishing_logs', ['platform'], unique=False)
        op.create_index(op.f('ix_publishing_logs_status'), 'publishing_logs', ['status'], unique=False)
        op.create_index(op.f('ix_publishing_logs_created_at'), 'publishing_logs', ['created_at'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'publishing_logs' in tables:
        op.drop_index(op.f('ix_publishing_logs_created_at'), table_name='publishing_logs')
        op.drop_index(op.f('ix_publishing_logs_status'), table_name='publishing_logs')
        op.drop_index(op.f('ix_publishing_logs_platform'), table_name='publishing_logs')
        op.drop_index(op.f('ix_publishing_logs_publishing_job_id'), table_name='publishing_logs')
        op.drop_index(op.f('ix_publishing_logs_post_id'), table_name='publishing_logs')
        op.drop_table('publishing_logs')
