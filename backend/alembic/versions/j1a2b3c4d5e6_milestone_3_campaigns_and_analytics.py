"""milestone_3_campaigns_and_analytics

Revision ID: j1a2b3c4d5e6
Revises: i1a2b3c4d5e6
Create Date: 2026-09-16 23:55:00.000000

Milestone 3:
- Creates `campaigns` table for marketing campaign lifecycle management.
- Creates `post_metrics` table for granular content performance and real analytics.
- Adds `campaign_id` foreign key column on `posts` table (SET NULL on delete).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'j1a2b3c4d5e6'
down_revision: Union[str, None] = 'i1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Create `campaigns` table
    if 'campaigns' not in existing_tables:
        op.create_table(
            'campaigns',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('team_id', sa.String(length=36), nullable=True),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('platform', sa.String(length=100), nullable=False, server_default='multi'),
            sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
            sa.Column('budget', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
            sa.Column('revenue', sa.Numeric(precision=12, scale=2), nullable=True),
            sa.Column('conversions', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('objective', sa.String(length=100), nullable=False, server_default='Brand Awareness'),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint('budget >= 0', name='chk_campaign_budget_non_negative'),
            sa.CheckConstraint('end_date IS NULL OR start_date IS NULL OR end_date >= start_date', name='chk_campaign_end_date_after_start'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_campaigns_user_id'), 'campaigns', ['user_id'], unique=False)
        op.create_index(op.f('ix_campaigns_team_id'), 'campaigns', ['team_id'], unique=False)
        op.create_index(op.f('ix_campaigns_name'), 'campaigns', ['name'], unique=False)
        op.create_index(op.f('ix_campaigns_status'), 'campaigns', ['status'], unique=False)
        op.create_index(op.f('ix_campaigns_start_date'), 'campaigns', ['start_date'], unique=False)
        op.create_index(op.f('ix_campaigns_end_date'), 'campaigns', ['end_date'], unique=False)

    # 2. Add `campaign_id` to `posts` table
    post_columns = [col['name'] for col in inspector.get_columns('posts')]
    if 'campaign_id' not in post_columns:
        op.add_column('posts', sa.Column('campaign_id', sa.String(length=36), nullable=True))
        op.create_foreign_key(
            'fk_posts_campaign_id',
            'posts',
            'campaigns',
            ['campaign_id'],
            ['id'],
            ondelete='SET NULL'
        )
        op.create_index(op.f('ix_posts_campaign_id'), 'posts', ['campaign_id'], unique=False)

    # 3. Create `post_metrics` table
    if 'post_metrics' not in existing_tables:
        op.create_table(
            'post_metrics',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('post_id', sa.String(length=36), nullable=False),
            sa.Column('social_account_id', sa.String(length=36), nullable=True),
            sa.Column('platform', sa.String(length=50), nullable=False),
            sa.Column('impressions', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('reach', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('engagement', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('clicks', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('likes', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('comments', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('shares', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('video_views', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('is_real', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('captured_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['social_account_id'], ['social_accounts.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_post_metrics_post_id'), 'post_metrics', ['post_id'], unique=False)
        op.create_index(op.f('ix_post_metrics_social_account_id'), 'post_metrics', ['social_account_id'], unique=False)
        op.create_index(op.f('ix_post_metrics_platform'), 'post_metrics', ['platform'], unique=False)
        op.create_index(op.f('ix_post_metrics_captured_at'), 'post_metrics', ['captured_at'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'post_metrics' in existing_tables:
        op.drop_table('post_metrics')

    post_columns = [col['name'] for col in inspector.get_columns('posts')]
    if 'campaign_id' in post_columns:
        op.drop_constraint('fk_posts_campaign_id', 'posts', type_='foreignkey')
        op.drop_index(op.f('ix_posts_campaign_id'), table_name='posts')
        op.drop_column('posts', 'campaign_id')

    if 'campaigns' in existing_tables:
        op.drop_table('campaigns')
