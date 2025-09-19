"""
Initialize database schema from models
"""
import asyncio
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config.database import db_manager, Base
from models.database import (
    User, Group, UserGroupMembership, Tenant, Department,
    Provider, ProviderModel, TenantProviderConfig,
    Tool, TenantToolConfig,
    WorkflowAgent, ChatSession, Document, DocumentFolder,
    Chat, Message
)

async def init_db():
    """Initialize database schema"""
    try:
        print(" Initializing database manager...")

        # Initialize database manager
        await db_manager.initialize()

        print(" Creating database schema...")

        # Create all tables
        async with db_manager.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        print("Database schema initialized successfully!")
        print("📋 Created tables:")
        print("   • Users, Groups, Tenants, Departments")
        print("   • Providers, ProviderModels, TenantProviderConfigs")
        print("   • Tools, TenantToolConfigs, AgentToolConfigs")
        print("   • WorkflowAgents, ChatSessions, Documents, DocumentFolders")
        print("   • Chats, Messages")

    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(init_db())
