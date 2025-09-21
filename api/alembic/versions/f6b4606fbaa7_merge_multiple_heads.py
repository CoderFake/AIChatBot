"""Merge multiple heads

Revision ID: f6b4606fbaa7
Revises: 5e4b957a8abf, drop_dept_tool_configs
Create Date: 2025-09-16 16:54:13.801439

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6b4606fbaa7'
down_revision: Union[str, Sequence[str], None] = ('5e4b957a8abf', 'drop_dept_tool_configs')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
