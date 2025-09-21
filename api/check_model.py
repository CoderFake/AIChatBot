#!/usr/bin/env python3
"""
Script to check WorkflowAgent model configuration for a tenant
"""

import asyncio
import sys
import os

# Add the api directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

from config.database import init_db, get_db_context
from services.agents.workflow_agent_service import WorkflowAgentService
from services.llm.provider_manager import LLMProviderManager


async def check_workflow_agent_model(tenant_id: str):
    """Check WorkflowAgent model for tenant"""
    try:
        print(f"🔍 Checking WorkflowAgent model for tenant: {tenant_id}")

        async with get_db_context() as db:
            service = WorkflowAgentService(db)
            agent = await service.get_or_create_workflow_agent(tenant_id)

            if agent:
                print(f"✅ WorkflowAgent found:")
                print(f"   ID: {agent.get('id')}")
                print(f"   Model Name: {agent.get('model_name')}")
                print(f"   Provider Name: {agent.get('provider_name')}")
                print(f"   Is Enabled: {agent.get('is_enabled')}")

                # Check provider configuration
                print(f"\n🔍 Checking provider configuration...")
                provider_manager = LLMProviderManager()
                provider_config = await provider_manager.get_provider_config_for_tenant(tenant_id, db)

                if provider_config:
                    print(f"✅ Provider config found:")
                    print(f"   Base URL: {provider_config.config.get('base_url')}")
                    print(f"   Default Model: {provider_config.default_model}")
                    print(f"   Provider Name: {provider_config.name}")

                    # Try to get provider instance to check available models
                    print(f"\n🔍 Testing provider initialization...")
                    provider = await provider_manager.get_llm_provider_for_tenant(tenant_id, db)
                    if provider:
                        print(f"✅ Provider initialized successfully")
                        if hasattr(provider, '_available_models'):
                            print(f"   Available Models: {provider._available_models}")

                            # Check if the model from WorkflowAgent is available
                            agent_model = agent.get('model_name')
                            if agent_model in provider._available_models:
                                print(f"✅ Model '{agent_model}' is available in Ollama")
                            else:
                                print(f"❌ Model '{agent_model}' is NOT available in Ollama")
                                print(f"   Available models: {provider._available_models}")
                    else:
                        print(f"❌ Failed to initialize provider")

                return True
            else:
                print(f"❌ No WorkflowAgent found for tenant {tenant_id}")
                return False

    except Exception as e:
        print(f"❌ Error checking WorkflowAgent: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main function"""
    if len(sys.argv) != 2:
        print("Usage: python check_model.py <tenant_id>")
        sys.exit(1)

    tenant_id = sys.argv[1]

    # Initialize database
    await init_db()

    # Check the model
    await check_workflow_agent_model(tenant_id)


if __name__ == "__main__":
    asyncio.run(main())
