"""add access_level column to tools table

Revision ID: 5e4b957a8abf
Revises: 5c7a70aafa78
Create Date: 2025-09-13 18:32:53.420772

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5e4b957a8abf'
down_revision: Union[str, Sequence[str], None] = '5c7a70aafa78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add access_level column to tools table
    op.add_column('tools', sa.Column(
        'access_level',
        sa.String(20),
        nullable=True,
        default="both",
        comment="Access level: 'public', 'private', 'both'"
    ))

    # Update existing records to have default value
    op.execute("UPDATE tools SET access_level = 'both' WHERE access_level IS NULL")

    # Make column NOT NULL
    op.alter_column('tools', 'access_level', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    pass
