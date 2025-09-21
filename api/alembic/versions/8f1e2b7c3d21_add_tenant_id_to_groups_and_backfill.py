"""add tenant_id to groups and backfill

Revision ID: 8f1e2b7c3d21
Revises: 7a2d4c1e8b90
Create Date: 2025-08-14 21:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f1e2b7c3d21'
down_revision: Union[str, Sequence[str], None] = '7a2d4c1e8b90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('groups', sa.Column('tenant_id', sa.UUID(), nullable=True, comment='Tenant ID'))
    op.create_index('idx_group_tenant', 'groups', ['tenant_id'], unique=False)

    # Backfill tenant_id for groups using department -> tenant
    op.execute(
        """
        UPDATE groups g
        SET tenant_id = d.tenant_id
        FROM departments d
        WHERE g.department_id = d.id AND g.tenant_id IS NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_group_tenant', table_name='groups')
    op.drop_column('groups', 'tenant_id')


