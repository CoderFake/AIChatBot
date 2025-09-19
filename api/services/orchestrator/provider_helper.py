"""
Provider Helper for Workflow Nodes
Centralized helper to get providers via orchestrator
"""

from typing import Optional, Dict, Any
from services.orchestrator.orchestrator import Orchestrator
from utils.logging import get_logger

logger = get_logger(__name__)


class ProviderHelper:
    """
    Helper class for workflow nodes to get providers via orchestrator
    Implements the flow: nodes -> orchestrator -> workflow_agent_service -> provider_manager
    """
    
    @staticmethod
    async def get_provider_for_tenant(tenant_id: str, db=None):
        """
        Get LLM provider for tenant via orchestrator
        
        Args:
            tenant_id: Tenant ID
            db: Database session (optional)
            
        Returns:
            LLM provider instance or None
        """
        try:
            if not tenant_id:
                logger.warning("No tenant_id provided")
                return None
                
            orchestrator = Orchestrator(db)
            provider = await orchestrator.get_provider_for_tenant(tenant_id)
            
            if provider:
                logger.debug(f"Successfully got provider for tenant {tenant_id}")
            else:
                logger.warning(f"No provider available for tenant {tenant_id}")
                
            return provider
            
        except Exception as e:
            logger.error(f"Failed to get provider for tenant {tenant_id}: {e}")
            return None
    
    @staticmethod
    async def get_workflow_config_for_tenant(tenant_id: str, db=None) -> Optional[Dict[str, Any]]:
        """
        Get workflow configuration for tenant via orchestrator
        
        Args:
            tenant_id: Tenant ID
            db: Database session (optional)
            
        Returns:
            Workflow configuration dict or None
        """
        try:
            if not tenant_id:
                logger.warning("No tenant_id provided")
                return None
                
            orchestrator = Orchestrator(db)
            await orchestrator._ensure_initialized()
            
            config = await orchestrator._get_workflow_config(tenant_id)
            
            if config:
                logger.debug(f"Successfully got workflow config for tenant {tenant_id}")
            else:
                logger.warning(f"No workflow config available for tenant {tenant_id}")
                
            return config
            
        except Exception as e:
            logger.error(f"Failed to get workflow config for tenant {tenant_id}: {e}")
            return None
    
    @staticmethod
    async def invoke_llm_for_tenant(
        tenant_id: str,
        prompt: str,
        db=None,
        **kwargs
    ) -> Optional[str]:
        """
        Invoke LLM for tenant with automatic provider resolution

        Args:
            tenant_id: Tenant ID
            prompt: Prompt to send to LLM
            db: Database session (optional)
            **kwargs: Additional arguments for LLM

        Returns:
            LLM response content or None
        """
        try:
            provider = await ProviderHelper.get_provider_for_tenant(tenant_id, db)
            
            if not provider:
                logger.error(f"No provider available for tenant {tenant_id}")
                return None
                
            config = await ProviderHelper.get_workflow_config_for_tenant(tenant_id, db)
            
            if config:
                model_name = config.get("model_name")
                model_config = config.get("model_config", {})
                
                invoke_kwargs = {**model_config, **kwargs}
                
                response = await provider.ainvoke(prompt, model=model_name, **invoke_kwargs)
                return response.content.strip()
            else:
                response = await provider.ainvoke(prompt, **kwargs)
                return response.content.strip()
                
        except Exception as e:
            logger.error(f"Failed to invoke LLM for tenant {tenant_id}: {e}")
            return None


async def get_provider_for_tenant(tenant_id: str, db=None):
    """Convenience function to get provider for tenant"""
    return await ProviderHelper.get_provider_for_tenant(tenant_id, db)


async def invoke_llm_for_tenant(tenant_id: str, prompt: str, db=None, **kwargs) -> Optional[str]:
    """Convenience function to invoke LLM for tenant"""
    return await ProviderHelper.invoke_llm_for_tenant(tenant_id, prompt, db, **kwargs)


async def get_workflow_config_for_tenant(tenant_id: str, db=None) -> Optional[Dict[str, Any]]:
    """Convenience function to get workflow config for tenant"""
    return await ProviderHelper.get_workflow_config_for_tenant(tenant_id, db)
