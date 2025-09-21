"""user unique (tenant_id, username) and tenant subdomain unique

Revision ID: 9c4a1f2d7b11
Revises: 8f1e2b7c3d21
Create Date: 2025-08-14 21:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c4a1f2d7b11'
down_revision: Union[str, Sequence[str], None] = '8f1e2b7c3d21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop existing unique constraint on username if exists
    # Common auto-names: users_username_key (PostgreSQL default)
    op.execute('ALTER TABLE users DROP CONSTRAINT IF EXISTS users_username_key')
    op.execute('ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_users_username')

    # Create unique constraint on (tenant_id, username)
    op.create_unique_constraint('uq_user_tenant_username', 'users', ['tenant_id', 'username'])

    # Create unique constraint on tenant sub_domain
    op.execute('ALTER TABLE tenants DROP CONSTRAINT IF EXISTS uq_tenant_sub_domain')
    op.create_unique_constraint('uq_tenant_sub_domain', 'tenants', ['sub_domain'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_tenant_sub_domain', 'tenants', type_='unique')
    op.drop_constraint('uq_user_tenant_username', 'users', type_='unique')

