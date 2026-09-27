"""notification_module

Revision ID: k1a2b3c4d5e6
Revises: j1a2b3c4d5e6
Create Date: 2026-09-17 01:55:00.000000

Milestone 4 (Notification Module):
- Creates `notifications` table with idempotency key, user isolation, entity links, and JSON metadata.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'k1a2b3c4d5e6'
down_revision: Union[str, None] = 'j1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'notifications' not in existing_tables:
        op.create_table(
            'notifications',
            sa.Column('id', sa.String(36), nullable=False),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('type', sa.String(64), nullable=False),
            sa.Column('title', sa.String(255), nullable=False),
            sa.Column('message', sa.Text(), nullable=False),
            sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.text('FALSE')),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
            sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('related_entity_type', sa.String(64), nullable=True),
            sa.Column('related_entity_id', sa.String(36), nullable=True),
            sa.Column('meta_data', sa.JSON(), nullable=True),
            sa.Column('idempotency_key', sa.String(255), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'idempotency_key', name='uq_notification_user_idempotency'),
        )

        # Create indexes
        existing_indexes = []
        try:
            existing_indexes = [idx['name'] for idx in inspector.get_indexes('notifications')]
        except Exception:
            pass

        if 'ix_notifications_user_id' not in existing_indexes:
            op.create_index('ix_notifications_user_id', 'notifications', ['user_id'])
        if 'ix_notifications_type' not in existing_indexes:
            op.create_index('ix_notifications_type', 'notifications', ['type'])
        if 'ix_notifications_is_read' not in existing_indexes:
            op.create_index('ix_notifications_is_read', 'notifications', ['is_read'])
        if 'ix_notifications_created_at' not in existing_indexes:
            op.create_index('ix_notifications_created_at', 'notifications', ['created_at'])
        if 'ix_notifications_user_is_read' not in existing_indexes:
            op.create_index('ix_notifications_user_is_read', 'notifications', ['user_id', 'is_read'])
        if 'ix_notifications_idempotency_key' not in existing_indexes:
            op.create_index('ix_notifications_idempotency_key', 'notifications', ['idempotency_key'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()
    if 'notifications' in existing_tables:
        op.drop_table('notifications')
