"""Merge multiple heads

Revision ID: 5c7a70aafa78
Revises: 2500e400bcd5, 9c4a1f2d7b11
Create Date: 2025-09-13 18:30:09.080915

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c7a70aafa78'
down_revision: Union[str, Sequence[str], None] = ('2500e400bcd5', '9c4a1f2d7b11')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
