"""
Workflow Agent Service
Handles workflow agent management for tenants
"""
import uuid
from typing import Dict, Any, Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, insert
from sqlalchemy.orm import selectinload

from models.database.agent import WorkflowAgent
from models.database.tenant import Tenant
from models.database.provider import Provider
from services.cache.cache_manager import cache_manager
from services.llm.provider_service import ProviderService
from utils.logging import get_logger

logger = get_logger(__name__)


class WorkflowAgentService:
    """
    Service for managing workflow agents
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._cache_initialized = False

    async def _ensure_cache_initialized(self):
        """Ensure cache manager is initialized"""
        if not self._cache_initialized:
            self._cache_initialized = True

    async def get_or_create_workflow_agent(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get existing workflow agent or create new one for tenant
        """
        try:
            await self._ensure_cache_initialized()
            cache_key = f"workflow_agent_{tenant_id}"

            cached_agent = await cache_manager.get(cache_key)
            if cached_agent:
                logger.info(f"Retrieved workflow agent from cache for tenant {tenant_id}")
                return cached_agent

            stmt = select(WorkflowAgent).where(WorkflowAgent.tenant_id == uuid.UUID(tenant_id))
            result = await self.db.execute(stmt)
            workflow_agent = result.scalar_one_or_none()

            if not workflow_agent:
                logger.info(f"No workflow agent found for tenant {tenant_id}, creating default")
                try:
                    workflow_agent = await self._create_default_workflow_agent(tenant_id)
                except Exception as create_error:
                    logger.error(f"Failed to create default workflow agent for tenant {tenant_id}: {create_error}")
                    return await self._get_fallback_workflow_config(tenant_id)

            agent_data = {
                "id": str(workflow_agent.id),
                "tenant_id": str(workflow_agent.tenant_id),
                "provider_name": workflow_agent.provider_name,
                "model_name": workflow_agent.model_name,
                "model_config": workflow_agent.model_config or {},
                "max_iterations": workflow_agent.max_iterations,
                "timeout_seconds": workflow_agent.timeout_seconds,
                "confidence_threshold": workflow_agent.confidence_threshold,
                "is_active": workflow_agent.is_active,
                "created_at": workflow_agent.created_at.isoformat(),
                "updated_at": workflow_agent.updated_at.isoformat()
            }

            await cache_manager.set(cache_key, agent_data, ttl=None)
            logger.info(f"Cached workflow agent for tenant {tenant_id}")

            return agent_data

        except Exception as e:
            logger.error(f"Failed to get/create workflow agent for tenant {tenant_id}: {e}")
            raise

    async def _create_default_workflow_agent(self, tenant_id: str) -> WorkflowAgent:
        """
        Create default workflow agent for tenant
        """
        try:
            available_providers = await self._get_available_providers(tenant_id)

            default_provider = available_providers[0] if available_providers else "gemini"
            default_model = "gemini-pro" if default_provider == "gemini" else "gpt-4"

            workflow_agent = WorkflowAgent(
                tenant_id=uuid.UUID(tenant_id),
                provider_name=default_provider,
                model_name=default_model,
                model_config={
                    "temperature": 0.7,
                    "max_tokens": 2048,
                    "top_p": 0.9
                },
                max_iterations=10,
                timeout_seconds=300,
                confidence_threshold=0.7,
                is_active=True
            )

            self.db.add(workflow_agent)
            await self.db.commit()
            await self.db.refresh(workflow_agent)

            logger.info(f"Created default workflow agent for tenant {tenant_id}")
            return workflow_agent

        except Exception as e:
            logger.error(f"Failed to create default workflow agent for tenant {tenant_id}: {e}")
            await self.db.rollback()
            raise

    async def update_workflow_agent(
        self,
        tenant_id: str,
        provider_name: str,
        model_name: str,
        model_config: Optional[Dict[str, Any]] = None,
        max_iterations: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
        confidence_threshold: Optional[float] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Update workflow agent configuration
        """
        try:
            # Validate provider and model availability
            await self._validate_provider_model(tenant_id, provider_name, model_name)

            # Get current workflow agent
            stmt = select(WorkflowAgent).where(WorkflowAgent.tenant_id == uuid.UUID(tenant_id))
            result = await self.db.execute(stmt)
            workflow_agent = result.scalar_one_or_none()

            if not workflow_agent:
                raise ValueError(f"Workflow agent not found for tenant {tenant_id}")

            # Update fields
            update_data = {}
            if provider_name is not None:
                update_data["provider_name"] = provider_name
            if model_name is not None:
                update_data["model_name"] = model_name
            if model_config is not None:
                update_data["model_config"] = model_config
            if max_iterations is not None:
                update_data["max_iterations"] = max_iterations
            if timeout_seconds is not None:
                update_data["timeout_seconds"] = timeout_seconds
            if confidence_threshold is not None:
                update_data["confidence_threshold"] = confidence_threshold
            if is_active is not None:
                update_data["is_active"] = is_active

            # Update database
            stmt = (
                update(WorkflowAgent)
                .where(WorkflowAgent.id == workflow_agent.id)
                .values(**update_data)
            )
            await self.db.execute(stmt)
            await self.db.commit()

            # Refresh the object
            await self.db.refresh(workflow_agent)

            # Invalidate cache
            await self._invalidate_agent_cache(tenant_id)

            # Return updated data
            updated_data = {
                "id": str(workflow_agent.id),
                "tenant_id": str(workflow_agent.tenant_id),
                "provider_name": workflow_agent.provider_name,
                "model_name": workflow_agent.model_name,
                "model_config": workflow_agent.model_config or {},
                "max_iterations": workflow_agent.max_iterations,
                "timeout_seconds": workflow_agent.timeout_seconds,
                "confidence_threshold": workflow_agent.confidence_threshold,
                "is_active": workflow_agent.is_active,
                "created_at": workflow_agent.created_at.isoformat(),
                "updated_at": workflow_agent.updated_at.isoformat()
            }

            logger.info(f"Updated workflow agent for tenant {tenant_id}")
            return updated_data

        except Exception as e:
            logger.error(f"Failed to update workflow agent for tenant {tenant_id}: {e}")
            await self.db.rollback()
            raise

    async def _validate_provider_model(self, tenant_id: str, provider_name: str, model_name: str) -> None:
        """
        Validate that provider and model are available for tenant
        """
        available_providers = await self._get_available_providers(tenant_id)

        if provider_name not in available_providers:
            raise ValueError(f"Provider {provider_name} is not available for tenant {tenant_id}")

        # Get provider models
        provider_models = await self._get_provider_models(tenant_id, provider_name)

        if model_name not in provider_models:
            raise ValueError(f"Model {model_name} is not available for provider {provider_name}")

    async def _get_available_providers(self, tenant_id: str) -> List[str]:
        """
        Get list of available providers for tenant
        """
        try:
            stmt = select(Provider).where(
                Provider.tenant_id == uuid.UUID(tenant_id),
                Provider.is_active == True
            )
            result = await self.db.execute(stmt)
            providers = result.scalars().all()

            return [provider.name for provider in providers]

        except Exception as e:
            logger.error(f"Failed to get available providers for tenant {tenant_id}: {e}")
            return ["gemini"]  # Fallback

    async def _get_provider_models(self, tenant_id: str, provider_name: str) -> List[str]:
        """
        Get list of available models for provider
        """
        try:
            # This would typically query provider configurations or use provider service
            # For now, return common models based on provider
            if provider_name.lower() == "gemini":
                return ["gemini-pro", "gemini-pro-vision", "gemini-1.5-pro"]
            elif provider_name.lower() == "openai":
                return ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]
            elif provider_name.lower() == "anthropic":
                return ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]
            else:
                return [f"{provider_name}-default"]

        except Exception as e:
            logger.error(f"Failed to get models for provider {provider_name}: {e}")
            return [f"{provider_name}-default"]

    async def get_workflow_agent_config(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get complete workflow agent configuration including provider and API keys for orchestrator
        Cache-first approach
        """
        try:
            workflow_agent = await self.get_or_create_workflow_agent(tenant_id)
            
            provider_config = await self._get_tenant_provider_config(tenant_id, workflow_agent["provider_name"])
            
            return {
                "provider_name": workflow_agent["provider_name"],
                "model_name": workflow_agent["model_name"],
                "model_config": workflow_agent["model_config"],
                "max_iterations": workflow_agent["max_iterations"],
                "timeout_seconds": workflow_agent["timeout_seconds"],
                "confidence_threshold": workflow_agent["confidence_threshold"],
                "is_active": workflow_agent["is_active"]
            }

        except Exception as e:
            logger.error(f"Failed to get workflow agent config for tenant {tenant_id}: {e}")
            raise
    
    async def _get_tenant_provider_config(self, tenant_id: str, provider_name: str) -> Dict[str, Any]:
        """
        Get tenant provider configuration including API keys
        Cache-first approach
        """
        try:
            cache_key = f"tenant_provider_config:{tenant_id}:{provider_name}"
            
            cached_config = await cache_manager.get(cache_key)
            if cached_config:
                api_keys = cached_config.get("api_keys", [])
                return cached_config
            
            # Query database
            from models.database.provider import TenantProviderConfig, Provider
            from sqlalchemy import select
            import uuid
            
            provider_result = await self.db.execute(
                select(TenantProviderConfig, Provider)
                .join(Provider, Provider.id == TenantProviderConfig.provider_id)
                .where(
                    TenantProviderConfig.tenant_id == uuid.UUID(tenant_id),
                    Provider.provider_name == provider_name,
                    TenantProviderConfig.is_enabled == True
                )
            )
            provider_data = provider_result.first()
            
            if not provider_data:
                logger.warning(f"No enabled provider config found for {provider_name} in tenant {tenant_id}")
                # Return fallback config
                fallback_config = {
                    "api_keys": [],
                    "base_config": {},
                    "is_fallback": True,
                    "rate_limit_config": {}
                }
                await cache_manager.set(cache_key, fallback_config, ttl=1800)
                return fallback_config
            
            tenant_config, provider = provider_data
            
            api_keys = tenant_config.api_keys or []
            logger.info(f"Provider config for {provider_name}: api_keys type={type(api_keys)}, value={api_keys}, length={len(api_keys) if api_keys else 0}")

            provider_config = {
                "api_keys": api_keys,
                "base_config": provider.base_config or {},
                "is_fallback": False,
                "rate_limit_config": getattr(tenant_config, 'rate_limit_config', {}) or {},
                "provider_display_name": getattr(provider, 'display_name', ''),
                "provider_description": getattr(provider, 'description', '')
            }
            
            # Cache the config
            await cache_manager.set(cache_key, provider_config, ttl=None)
            logger.info(f"Cached provider config for tenant {tenant_id}, provider {provider_name}")
            
            return provider_config
            
        except Exception as e:
            logger.error(f"Failed to get tenant provider config for {tenant_id}, {provider_name}: {e}")
            # Return minimal fallback
            return {
                "api_keys": [],
                "base_config": {},
                "is_fallback": True,
                "rate_limit_config": {}
            }

    async def _invalidate_agent_cache(self, tenant_id: str) -> None:
        """
        Invalidate workflow agent cache for tenant
        """
        try:
            await self._ensure_cache_initialized()
            cache_key = f"workflow_agent_{tenant_id}"
            await cache_manager.delete(cache_key)
            logger.info(f"Invalidated workflow agent cache for tenant {tenant_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate workflow agent cache for tenant {tenant_id}: {e}")

    async def _get_fallback_workflow_config(self, tenant_id: str) -> Dict[str, Any]:
        """
        Get fallback workflow configuration when database is not available
        """
        logger.warning(f"Using fallback workflow config for tenant {tenant_id}")

        # Try to get available providers
        available_providers = await self._get_available_providers(tenant_id)

        # Choose first available provider or default
        if available_providers:
            provider_name = available_providers[0]
        else:
            provider_name = "gemini"  # Default fallback

        # Set appropriate model based on provider
        if provider_name == "gemini":
            model_name = "gemini-2.0-flash"
        elif provider_name == "openai":
            model_name = "gpt-4"
        else:
            model_name = f"{provider_name}-default"

        return {
            "id": f"fallback-{tenant_id}",
            "tenant_id": tenant_id,
            "provider_name": provider_name,
            "model_name": model_name,
            "model_config": {
                "temperature": 0.7,
                "max_tokens": 2048,
                "top_p": 0.9
            },
            "max_iterations": 10,
            "timeout_seconds": 300,
            "confidence_threshold": 0.7,
            "is_active": True,
            "created_at": "2025-01-01T00:00:00.000000",
            "updated_at": "2025-01-01T00:00:00.000000"
        }

    async def get_available_providers_with_models(self, tenant_id: str) -> List[Dict[str, Any]]:
        """
        Get available providers with their models for tenant
        """
        try:
            providers = await self._get_available_providers(tenant_id)
            result = []

            for provider_name in providers:
                models = await self._get_provider_models(tenant_id, provider_name)
                result.append({
                    "name": provider_name,
                    "models": models
                })

            return result

        except Exception as e:
            logger.error(f"Failed to get providers with models for tenant {tenant_id}: {e}")
            return []
