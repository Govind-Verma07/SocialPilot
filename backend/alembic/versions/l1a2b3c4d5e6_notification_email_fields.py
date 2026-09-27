"""notification_email_fields

Revision ID: l1a2b3c4d5e6
Revises: k1a2b3c4d5e6
Create Date: 2026-09-17 15:10:00.000000

Notification Module (Real Email Notification System):
- Adds `email_status`, `email_sent_at`, and `email_error` columns to `notifications` table.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'l1a2b3c4d5e6'
down_revision: Union[str, None] = 'k1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'notifications' in existing_tables:
        columns = [col['name'] for col in inspector.get_columns('notifications')]
        if 'email_status' not in columns:
            op.add_column('notifications', sa.Column('email_status', sa.String(32), nullable=True))
            op.create_index('ix_notifications_email_status', 'notifications', ['email_status'])
        if 'email_sent_at' not in columns:
            op.add_column('notifications', sa.Column('email_sent_at', sa.DateTime(timezone=True), nullable=True))
        if 'email_error' not in columns:
            op.add_column('notifications', sa.Column('email_error', sa.Text(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if 'notifications' in existing_tables:
        columns = [col['name'] for col in inspector.get_columns('notifications')]
        if 'email_status' in columns:
            try:
                op.drop_index('ix_notifications_email_status', table_name='notifications')
            except Exception:
                pass
            op.drop_column('notifications', 'email_status')
        if 'email_sent_at' in columns:
            op.drop_column('notifications', 'email_sent_at')
        if 'email_error' in columns:
            op.drop_column('notifications', 'email_error')
