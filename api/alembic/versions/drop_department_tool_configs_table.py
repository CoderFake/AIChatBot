"""Drop department_tool_configs table - replaced by agent_tool_configs

Revision ID: drop_department_tool_configs_table
Revises: add_access_level_to_agent_tool_config
Create Date: 2025-09-16 03:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'drop_dept_tool_configs'
down_revision: Union[str, None] = 'add_access_level_to_agent'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop department_tool_configs table as it's been replaced by agent_tool_configs"""

    # Drop the table if it exists
    op.drop_table('department_tool_configs', if_exists=True)

    # Note: All department-level tool configurations should now be handled
    # through agent_tool_configs with access_level_override field


def downgrade() -> None:
    """Recreate department_tool_configs table"""

    op.create_table('department_tool_configs',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('version', sa.String(length=20), server_default=sa.text("'1.0.0'"), nullable=False),
        sa.Column('metadata_', sa.String(), nullable=True),
        sa.Column('department_id', sa.UUID(), nullable=False),
        sa.Column('tool_id', sa.UUID(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
        sa.Column('access_level_override', sa.String(length=20), nullable=True),
        sa.Column('config_data', sa.JSON(), nullable=True),
        sa.Column('usage_limits', sa.JSON(), nullable=True),
        sa.Column('configured_by', sa.UUID(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_dept_tool_enabled', 'department_id', 'is_enabled'),
        sa.Index('idx_dept_tool_override', 'department_id', 'access_level_override')
    )

    # Recreate foreign key constraints
    op.create_foreign_key('fk_department_tool_configs_department_id', 'department_tool_configs', 'departments', ['department_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_department_tool_configs_tool_id', 'department_tool_configs', 'tools', ['tool_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_department_tool_configs_configured_by', 'department_tool_configs', 'users', ['configured_by'], ['id'], ondelete='SET NULL')
