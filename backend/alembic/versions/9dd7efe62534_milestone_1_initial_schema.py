"""milestone_1_initial_schema

Revision ID: 9dd7efe62534
Revises: 
Create Date: 2026-08-26 13:25:11.738376

Milestone 1 Schema:
  - Adds `role` column to existing `users` table
  - Creates: teams, user_settings, social_accounts, team_members,
             account_permissions, account_sync_logs
  - All PostgreSQL ENUM types are created explicitly before use,
    and `create_type=False` is set on inline column definitions to prevent
    duplicate-type errors.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9dd7efe62534'
down_revision: Union[str, None] = '8d0eb72eda8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Create all PostgreSQL ENUM types (checkfirst=True is safe here) ──
    userrole_enum = postgresql.ENUM(
        'content_creator', 'marketing_team', 'business_user', 'administrator',
        name='userrole', create_type=False
    )
    socialplatform_enum = postgresql.ENUM(
        'facebook', 'instagram', 'linkedin', 'x', 'youtube', 'pinterest',
        name='socialplatform', create_type=False
    )
    accountstatus_enum = postgresql.ENUM(
        'connected', 'disconnected', 'pending', 'error', 'token_expired',
        name='accountstatus', create_type=False
    )
    syncstatus_enum = postgresql.ENUM(
        'success', 'failed', 'pending',
        name='syncstatus', create_type=False
    )
    teammemberrole_enum = postgresql.ENUM(
        'owner', 'admin', 'member', 'viewer',
        name='teammemberrole', create_type=False
    )

    # Actually create the types in the DB
    postgresql.ENUM(
        'content_creator', 'marketing_team', 'business_user', 'administrator',
        name='userrole'
    ).create(conn, checkfirst=True)
    postgresql.ENUM(
        'facebook', 'instagram', 'linkedin', 'x', 'youtube', 'pinterest',
        name='socialplatform'
    ).create(conn, checkfirst=True)
    postgresql.ENUM(
        'connected', 'disconnected', 'pending', 'error', 'token_expired',
        name='accountstatus'
    ).create(conn, checkfirst=True)
    postgresql.ENUM(
        'success', 'failed', 'pending',
        name='syncstatus'
    ).create(conn, checkfirst=True)
    postgresql.ENUM(
        'owner', 'admin', 'member', 'viewer',
        name='teammemberrole'
    ).create(conn, checkfirst=True)

    # ── 2. teams ─────────────────────────────────────────────────────────────
    op.create_table('teams',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('owner_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_teams_owner_id'), 'teams', ['owner_id'], unique=False)

    # ── 3. user_settings ─────────────────────────────────────────────────────
    op.create_table('user_settings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('email_notifications', sa.Boolean(), nullable=False),
        sa.Column('timezone', sa.String(length=50), nullable=False),
        sa.Column('extra', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_settings_user_id'), 'user_settings', ['user_id'], unique=True)

    # ── 4. social_accounts (use create_type=False — types already exist) ─────
    op.create_table('social_accounts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('team_id', sa.String(length=36), nullable=True),
        sa.Column('platform', socialplatform_enum, nullable=False),
        sa.Column('platform_account_id', sa.String(length=255), nullable=False),
        sa.Column('account_name', sa.String(length=255), nullable=False),
        sa.Column('account_username', sa.String(length=255), nullable=False),
        sa.Column('status', accountstatus_enum, nullable=False),
        sa.Column('access_token_encrypted', sa.Text(), nullable=True),
        sa.Column('refresh_token_encrypted', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('connected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_social_accounts_platform'), 'social_accounts', ['platform'], unique=False)
    op.create_index(op.f('ix_social_accounts_team_id'), 'social_accounts', ['team_id'], unique=False)
    op.create_index(op.f('ix_social_accounts_user_id'), 'social_accounts', ['user_id'], unique=False)

    # ── 5. team_members ──────────────────────────────────────────────────────
    op.create_table('team_members',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('team_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('role', teammemberrole_enum, nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_team_members_team_id'), 'team_members', ['team_id'], unique=False)
    op.create_index(op.f('ix_team_members_user_id'), 'team_members', ['user_id'], unique=False)

    # ── 6. account_permissions ───────────────────────────────────────────────
    op.create_table('account_permissions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('social_account_id', sa.String(length=36), nullable=False),
        sa.Column('permission', sa.String(length=100), nullable=False),
        sa.Column('granted', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['social_account_id'], ['social_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_account_permissions_social_account_id'), 'account_permissions', ['social_account_id'], unique=False)

    # ── 7. account_sync_logs ─────────────────────────────────────────────────
    op.create_table('account_sync_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('social_account_id', sa.String(length=36), nullable=False),
        sa.Column('status', syncstatus_enum, nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('synced_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['social_account_id'], ['social_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_account_sync_logs_social_account_id'), 'account_sync_logs', ['social_account_id'], unique=False)
    op.create_index(op.f('ix_account_sync_logs_synced_at'), 'account_sync_logs', ['synced_at'], unique=False)

    # ── 8. Add role column to existing users table ───────────────────────────
    op.add_column(
        'users',
        sa.Column('role', userrole_enum, server_default='content_creator', nullable=False)
    )


def downgrade() -> None:
    conn = op.get_bind()

    # Drop column before dropping type
    op.drop_column('users', 'role')

    op.drop_index(op.f('ix_account_sync_logs_synced_at'), table_name='account_sync_logs')
    op.drop_index(op.f('ix_account_sync_logs_social_account_id'), table_name='account_sync_logs')
    op.drop_table('account_sync_logs')

    op.drop_index(op.f('ix_account_permissions_social_account_id'), table_name='account_permissions')
    op.drop_table('account_permissions')

    op.drop_index(op.f('ix_team_members_user_id'), table_name='team_members')
    op.drop_index(op.f('ix_team_members_team_id'), table_name='team_members')
    op.drop_table('team_members')

    op.drop_index(op.f('ix_social_accounts_user_id'), table_name='social_accounts')
    op.drop_index(op.f('ix_social_accounts_team_id'), table_name='social_accounts')
    op.drop_index(op.f('ix_social_accounts_platform'), table_name='social_accounts')
    op.drop_table('social_accounts')

    op.drop_index(op.f('ix_user_settings_user_id'), table_name='user_settings')
    op.drop_table('user_settings')

    op.drop_index(op.f('ix_teams_owner_id'), table_name='teams')
    op.drop_table('teams')

    # Drop ENUM types (after all referencing tables are gone)
    postgresql.ENUM(name='userrole').drop(conn, checkfirst=True)
    postgresql.ENUM(name='socialplatform').drop(conn, checkfirst=True)
    postgresql.ENUM(name='accountstatus').drop(conn, checkfirst=True)
    postgresql.ENUM(name='syncstatus').drop(conn, checkfirst=True)
    postgresql.ENUM(name='teammemberrole').drop(conn, checkfirst=True)
