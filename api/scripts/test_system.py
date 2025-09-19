#!/usr/bin/env python3
"""
Quick test to verify system is working
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the api directory to Python path
sys.path.insert(0, '/app')

from utils.logging import get_logger

logger = get_logger(__name__)


async def test_services():
    """Test basic services"""
    try:
        # Test database connection
        from config.database import init_db, test_connection
        await init_db()
        db_ok = await test_connection()
        print(f"✅ Database: {'OK' if db_ok else 'FAILED'}")

        # Test tool manager
        from services.tools.tool_manager import tool_manager
        await tool_manager.initialize()
        print("✅ Tool Manager: OK")

        # Test orchestrator
        from services.orchestrator.orchestrator import Orchestrator
        orchestrator = Orchestrator()
        await orchestrator._ensure_initialized()
        print("✅ Orchestrator: OK")

        print("\n🎉 All services initialized successfully!")
        return True

    except Exception as e:
        print(f"❌ Service test failed: {e}")
        return False


async def test_tenant_workflow(tenant_id: str):
    """Test tenant workflow configuration"""
    try:
        from services.orchestrator.orchestrator import Orchestrator

        orchestrator = Orchestrator()
        workflow_config = await orchestrator._get_workflow_config(tenant_id)

        if workflow_config:
            print(f"✅ Tenant {tenant_id} workflow config: {workflow_config.get('provider_name')} - {workflow_config.get('model_name')}")
            return True
        else:
            print(f"❌ Tenant {tenant_id} has no workflow config")
            return False

    except Exception as e:
        print(f"❌ Tenant workflow test failed: {e}")
        return False


async def main():
    """Main test function"""
    print("🚀 Testing AI ChatBot System...\n")

    # Test services
    services_ok = await test_services()

    if services_ok:
        # Test tenant workflow
        tenant_id = "b397ab8f-353e-4031-a6b5-549904bb698d"
        workflow_ok = await test_tenant_workflow(tenant_id)

        if workflow_ok:
            print("\n🎊 System is ready for queries!")
        else:
            print("\n⚠️  System needs workflow configuration")
    else:
        print("\n❌ System has critical issues")


if __name__ == "__main__":
    asyncio.run(main())
