"""add department tool config and access level override

Revision ID: 2500e400bcd5
Revises: 9c4a1f2d7b11
Create Date: 2025-09-13 17:32:44.662238

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2500e400bcd5'
down_revision: Union[str, Sequence[str], None] = None  # Start from base to avoid conflicts
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # DepartmentToolConfig table creation (deprecated - replaced by AgentToolConfig)
    op.create_table('department_tool_configs',
        sa.Column('id', sa.UUID(), nullable=False, comment='Primary key'),
        sa.Column('department_id', sa.UUID(), nullable=False, comment='Department ID'),
        sa.Column('tool_id', sa.UUID(), nullable=False, comment='Tool ID'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, default=True, comment='Whether tool is enabled for this department'),
        sa.Column('access_level_override', sa.String(20), nullable=True, comment="Department-specific access level override ('public', 'private', 'both', or NULL to use tool default)"),
        sa.Column('config_data', sa.JSON(), nullable=True, comment='Department-specific tool configuration (overrides tenant config)'),
        sa.Column('usage_limits', sa.JSON(), nullable=True, comment='Department-specific usage limits (overrides tenant limits)'),
        sa.Column('configured_by', sa.UUID(), nullable=True, comment='User who configured this tool for department'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), server_onupdate=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tool_id'], ['tools.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['configured_by'], ['users.id'], ondelete='SET NULL'),
        sa.Index('idx_dept_tool_enabled', 'department_id', 'is_enabled'),
        sa.Index('idx_dept_tool_override', 'department_id', 'access_level_override')
    )


def downgrade() -> None:
    """Downgrade schema."""
    pass
