"""phase_5_publishing_results

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-09-12 03:00:00.000000

Phase 5 Schema:
  - Creates table: post_publish_results
  - Adds necessary indexes and foreign keys
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if 'post_publish_results' not in existing_tables:
        op.create_table(
            'post_publish_results',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('post_id', sa.String(length=36), nullable=False),
            sa.Column('social_account_id', sa.String(length=36), nullable=True),
            sa.Column('platform', sa.String(length=50), nullable=False),
            sa.Column('status', sa.String(length=30), nullable=False, server_default='published'),
            sa.Column('platform_post_id', sa.String(length=255), nullable=True),
            sa.Column('published_url', sa.Text(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['social_account_id'], ['social_accounts.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_post_publish_results_post_id'), 'post_publish_results', ['post_id'], unique=False)
        op.create_index(op.f('ix_post_publish_results_social_account_id'), 'post_publish_results', ['social_account_id'], unique=False)
        op.create_index(op.f('ix_post_publish_results_platform'), 'post_publish_results', ['platform'], unique=False)
        op.create_index(op.f('ix_post_publish_results_status'), 'post_publish_results', ['status'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    if 'post_publish_results' in existing_tables:
        op.drop_index(op.f('ix_post_publish_results_status'), table_name='post_publish_results')
        op.drop_index(op.f('ix_post_publish_results_platform'), table_name='post_publish_results')
        op.drop_index(op.f('ix_post_publish_results_social_account_id'), table_name='post_publish_results')
        op.drop_index(op.f('ix_post_publish_results_post_id'), table_name='post_publish_results')
        op.drop_table('post_publish_results')
