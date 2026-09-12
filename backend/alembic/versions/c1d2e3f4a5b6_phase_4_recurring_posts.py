"""phase_4_recurring_posts

Revision ID: c1d2e3f4a5b6
Revises: b1c2d3e4f5a6
Create Date: 2026-09-12 02:40:00.000000

Phase 4 Schema:
  - Creates PostgreSQL enum type: recurrencefrequency ('daily', 'weekly', 'monthly')
  - Creates table: recurring_rules
  - Creates table: recurring_rule_social_accounts (junction table)
  - Adds column: posts.recurring_rule_id
  - Adds necessary indexes and foreign keys
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    insp = sa.inspect(conn)
    existing_tables = insp.get_table_names()

    # 1. Create recurrencefrequency enum type
    recurrencefrequency_enum = postgresql.ENUM(
        'daily', 'weekly', 'monthly',
        name='recurrencefrequency', create_type=False
    )
    postgresql.ENUM(
        'daily', 'weekly', 'monthly',
        name='recurrencefrequency'
    ).create(conn, checkfirst=True)

    # 2. Create recurring_rules table if not exists
    if 'recurring_rules' not in existing_tables:
        op.create_table(
            'recurring_rules',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('user_id', sa.String(length=36), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('media_urls', sa.JSON(), nullable=True),
            sa.Column('post_type', sa.String(length=50), nullable=False, server_default='text'),
            sa.Column('frequency', recurrencefrequency_enum, nullable=False),
            sa.Column('interval', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('by_weekday', sa.Integer(), nullable=True),
            sa.Column('by_month_day', sa.Integer(), nullable=True),
            sa.Column('start_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('end_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('occurrence_limit', sa.Integer(), nullable=True),
            sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_recurring_rules_user_id', 'recurring_rules', ['user_id'], unique=False)
        op.create_index('ix_recurring_rules_frequency', 'recurring_rules', ['frequency'], unique=False)
        op.create_index('ix_recurring_rules_start_at', 'recurring_rules', ['start_at'], unique=False)
        op.create_index('ix_recurring_rules_end_at', 'recurring_rules', ['end_at'], unique=False)
        op.create_index('ix_recurring_rules_next_run_at', 'recurring_rules', ['next_run_at'], unique=False)
        op.create_index('ix_recurring_rules_is_active', 'recurring_rules', ['is_active'], unique=False)

    # 3. Create recurring_rule_social_accounts junction table
    if 'recurring_rule_social_accounts' not in existing_tables:
        op.create_table(
            'recurring_rule_social_accounts',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('recurring_rule_id', sa.String(length=36), nullable=False),
            sa.Column('social_account_id', sa.String(length=36), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['recurring_rule_id'], ['recurring_rules.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['social_account_id'], ['social_accounts.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_recurring_rule_social_accounts_recurring_rule_id', 'recurring_rule_social_accounts', ['recurring_rule_id'], unique=False)
        op.create_index('ix_recurring_rule_social_accounts_social_account_id', 'recurring_rule_social_accounts', ['social_account_id'], unique=False)

    # 4. Add recurring_rule_id to posts table if not exists
    if 'posts' in existing_tables:
        post_cols = [c['name'] for c in insp.get_columns('posts')]
        if 'recurring_rule_id' not in post_cols:
            op.add_column('posts', sa.Column('recurring_rule_id', sa.String(length=36), nullable=True))
            op.create_foreign_key('fk_posts_recurring_rule_id_recurring_rules', 'posts', 'recurring_rules', ['recurring_rule_id'], ['id'], ondelete='CASCADE')
            op.create_index('ix_posts_recurring_rule_id', 'posts', ['recurring_rule_id'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()

    # Drop recurring_rule_id from posts
    op.drop_constraint('fk_posts_recurring_rule_id_recurring_rules', 'posts', type_='foreignkey')
    op.drop_index('ix_posts_recurring_rule_id', table_name='posts')
    op.drop_column('posts', 'recurring_rule_id')

    # Drop recurring_rule_social_accounts
    op.drop_index('ix_recurring_rule_social_accounts_social_account_id', table_name='recurring_rule_social_accounts')
    op.drop_index('ix_recurring_rule_social_accounts_recurring_rule_id', table_name='recurring_rule_social_accounts')
    op.drop_table('recurring_rule_social_accounts')

    # Drop recurring_rules
    op.drop_index('ix_recurring_rules_is_active', table_name='recurring_rules')
    op.drop_index('ix_recurring_rules_next_run_at', table_name='recurring_rules')
    op.drop_index('ix_recurring_rules_end_at', table_name='recurring_rules')
    op.drop_index('ix_recurring_rules_start_at', table_name='recurring_rules')
    op.drop_index('ix_recurring_rules_frequency', table_name='recurring_rules')
    op.drop_index('ix_recurring_rules_user_id', table_name='recurring_rules')
    op.drop_table('recurring_rules')

    postgresql.ENUM(
        'daily', 'weekly', 'monthly',
        name='recurrencefrequency'
    ).drop(conn, checkfirst=True)
