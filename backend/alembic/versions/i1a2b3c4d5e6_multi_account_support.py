"""multi_account_support_unique_constraint

Revision ID: i1a2b3c4d5e6
Revises: h1a2b3c4d5e6
Create Date: 2026-09-16 22:00:00.000000

Adds uq_social_accounts_user_platform_account unique constraint on
social_accounts (user_id, platform, platform_account_id) to support
multiple accounts per platform per user while preventing duplicate
connections of the exact same external account.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'i1a2b3c4d5e6'
down_revision: Union[str, None] = 'h1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Check if constraint already exists
    existing_constraints = [
        c['name'] for c in inspector.get_unique_constraints('social_accounts')
    ]
    if 'uq_social_accounts_user_platform_account' not in existing_constraints:
        op.create_unique_constraint(
            'uq_social_accounts_user_platform_account',
            'social_accounts',
            ['user_id', 'platform', 'platform_account_id']
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_constraints = [
        c['name'] for c in inspector.get_unique_constraints('social_accounts')
    ]
    if 'uq_social_accounts_user_platform_account' in existing_constraints:
        op.drop_constraint(
            'uq_social_accounts_user_platform_account',
            'social_accounts',
            type_='unique'
        )
