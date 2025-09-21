"""Add access_level_override and usage_limits to agent_tool_configs

Revision ID: add_access_level_to_agent_tool_config
Revises: 2500e400bcd5
Create Date: 2025-09-16 03:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_access_level_to_agent'
down_revision: Union[str, None] = '2500e400bcd5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add access_level_override and usage_limits columns to agent_tool_configs"""
    # Add access_level_override column
    op.add_column('agent_tool_configs',
        sa.Column('access_level_override', sa.String(length=20), nullable=True,
                 comment="Agent-specific access level override ('public', 'private', 'both')")
    )

    # Add usage_limits column
    op.add_column('agent_tool_configs',
        sa.Column('usage_limits', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
                 comment="Agent-specific usage limits")
    )

    # Add configured_by column
    op.add_column('agent_tool_configs',
        sa.Column('configured_by', postgresql.UUID(as_uuid=True), nullable=True,
                 comment="User who configured this tool for agent")
    )

    # Add foreign key constraint for configured_by
    op.create_foreign_key(
        'fk_agent_tool_configs_configured_by',
        'agent_tool_configs', 'users',
        ['configured_by'], ['id'],
        ondelete='SET NULL'
    )

    # Create index for access_level_override
    op.create_index(
        'idx_agent_tool_override',
        'agent_tool_configs',
        ['agent_id', 'access_level_override']
    )

    # Set default values for existing records
    op.execute("UPDATE agent_tool_configs SET access_level_override = 'both' WHERE access_level_override IS NULL")
    op.execute("UPDATE agent_tool_configs SET usage_limits = '{}' WHERE usage_limits IS NULL")


def downgrade() -> None:
    """Remove access_level_override and usage_limits columns from agent_tool_configs"""
    # Drop foreign key constraint
    op.drop_constraint('fk_agent_tool_configs_configured_by', 'agent_tool_configs', type_='foreignkey')

    # Drop index
    op.drop_index('idx_agent_tool_override', table_name='agent_tool_configs')

    # Drop columns
    op.drop_column('agent_tool_configs', 'configured_by')
    op.drop_column('agent_tool_configs', 'usage_limits')
    op.drop_column('agent_tool_configs', 'access_level_override')
