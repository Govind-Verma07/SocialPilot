"""phase_1_content_scheduling

Revision ID: b1c2d3e4f5a6
Revises: 9dd7efe62534
Create Date: 2026-09-12 02:00:00.000000

Phase 1 Schema:
  - Creates PostgreSQL enum type: poststatus ('draft', 'scheduled', 'published', 'failed')
  - Creates table: posts
  - Creates table: post_social_accounts (junction table)
  - Adds necessary indexes and foreign keys
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = '9dd7efe62534'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    # 1. Create poststatus enum type (checkfirst=True)
    poststatus_enum = postgresql.ENUM(
        'draft', 'scheduled', 'published', 'failed',
        name='poststatus', create_type=False
    )
    postgresql.ENUM(
        'draft', 'scheduled', 'published', 'failed',
        name='poststatus'
    ).create(conn, checkfirst=True)

    # 2. Create posts table if not exists
    if 'posts' not in existing_tables:
        op.create_table(
            'posts',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('team_id', sa.String(length=36), nullable=True),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('media_urls', sa.JSON(), nullable=True),
            sa.Column('post_type', sa.String(length=50), nullable=False, server_default='text'),
            sa.Column('status', poststatus_enum, nullable=False, server_default='draft'),
            sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_posts_user_id', 'posts', ['user_id'], unique=False)
        op.create_index('ix_posts_team_id', 'posts', ['team_id'], unique=False)
        op.create_index('ix_posts_status', 'posts', ['status'], unique=False)
        op.create_index('ix_posts_scheduled_at', 'posts', ['scheduled_at'], unique=False)
    else:
        existing_cols = [c['name'] for c in insp.get_columns('posts')]
        if 'team_id' not in existing_cols:
            op.add_column('posts', sa.Column('team_id', sa.String(length=36), nullable=True))
            op.create_foreign_key('fk_posts_team_id_teams', 'posts', 'teams', ['team_id'], ['id'], ondelete='SET NULL')
            op.create_index('ix_posts_team_id', 'posts', ['team_id'], unique=False)
        if 'published_at' not in existing_cols:
            op.add_column('posts', sa.Column('published_at', sa.DateTime(timezone=True), nullable=True))

    # 3. Create post_social_accounts junction table if not exists
    if 'post_social_accounts' not in existing_tables:
        op.create_table(
            'post_social_accounts',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('post_id', sa.String(length=36), nullable=False),
            sa.Column('social_account_id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['social_account_id'], ['social_accounts.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_post_social_accounts_post_id', 'post_social_accounts', ['post_id'], unique=False)
        op.create_index('ix_post_social_accounts_social_account_id', 'post_social_accounts', ['social_account_id'], unique=False)



def downgrade() -> None:
    conn = op.get_bind()

    op.drop_index('ix_post_social_accounts_social_account_id', table_name='post_social_accounts')
    op.drop_index('ix_post_social_accounts_post_id', table_name='post_social_accounts')
    op.drop_table('post_social_accounts')

    op.drop_index('ix_posts_scheduled_at', table_name='posts')
    op.drop_index('ix_posts_status', table_name='posts')
    op.drop_index('ix_posts_team_id', table_name='posts')
    op.drop_index('ix_posts_user_id', table_name='posts')
    op.drop_table('posts')

    postgresql.ENUM(
        'draft', 'scheduled', 'published', 'failed',
        name='poststatus'
    ).drop(conn, checkfirst=True)
