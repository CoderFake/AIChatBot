"""
Orchestrator Service - Simplified
Direct workflow system integration
No config, no fallback, no defaults
"""

from typing import Optional, Dict, Any
from utils.logging import get_logger

from services.llm.provider_manager import (
    DEFAULT_GEMINI_SAFETY_SETTINGS,
    DEFAULT_GEMINI_SYSTEM_INSTRUCTION,
)

logger = get_logger(__name__)

global_provider_manager = None
global_cache_manager = None


class Orchestrator:
    """
    Simplified orchestrator that directly uses the workflow system
    No configuration management, no fallback logic
    Uses global provider manager instance
    """

    def __init__(self, db=None):
        self.db = db
        self._cache_initialized = False

    async def _ensure_initialized(self):
        """Ensure basic initialization"""
        if not self._cache_initialized:
            self._cache_initialized = True

    async def llm(self, provider_name: str):
        """
        Get LLM provider wrapper với API keys injection
        Trả về wrapper object có method ainvoke(prompt, tenant_id, **kwargs)
        Uses global provider manager instance
        """
        global global_provider_manager

        if global_provider_manager is None:
            raise RuntimeError("Global provider manager not initialized. Make sure main.py initializes it.")

        provider = await global_provider_manager.get_provider(provider_name)
        return LLMProviderWrapper(provider)

    async def agents_structure(self, user_context: Dict[str, Any]):
        from services.agents.agent_service import AgentService
        if self.db is not None:
            agent_service = AgentService(self.db)
            return await agent_service.get_agents_structure_for_user(user_context)

        from config.database import get_db_context

        try:
            async with get_db_context() as db:
                agent_service = AgentService(db)
                return await agent_service.get_agents_structure_for_user(user_context)
        except Exception as exc:
            logger.error(f"Failed to load agents structure: {exc}")
            return {}

    def cache_manager(self):
        """
        Get global cache manager instance
        Returns the pre-initialized cache manager from main.py
        """
        global global_cache_manager
        if global_cache_manager is None:
            raise RuntimeError("Global cache manager not initialized. Make sure main.py initializes it.")
        return global_cache_manager

class LLMProviderWrapper:
    """Wrapper để inject API keys khi gọi ainvoke"""

    def __init__(self, provider):
        self.provider = provider

    async def ainvoke(self, prompt: str, tenant_id: str, model: Optional[str] = None, **kwargs):
        """Invoke LLM với API keys của tenant - chỉ truyền API keys, không re-initialize"""
        from services.providers.provider_api_keys_service import ProviderApiKeysService
        from config.database import get_db_context

        provider_kwargs = dict(kwargs)

        if tenant_id and self.provider:
            async with get_db_context() as db:
                api_keys_service = ProviderApiKeysService(db)
                api_keys_result = await api_keys_service.get_provider_api_keys(tenant_id, self.provider.name)
                tenant_api_keys = api_keys_result.get("api_keys", [])

                if not tenant_api_keys:
                    raise ValueError(f"No API keys found for tenant {tenant_id} and provider {self.provider.name}")

                provider_kwargs['api_keys'] = tenant_api_keys

        if self.provider and getattr(self.provider, "name", "") == "gemini":
            provider_kwargs = self._apply_gemini_overrides(provider_kwargs)

        return await self.provider.ainvoke(prompt, model, **provider_kwargs)

    def _apply_gemini_overrides(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Inject Gemini-specific configuration to reduce unnecessary safety blocks."""

        merged_kwargs = dict(kwargs)
        provider_config = getattr(self.provider, "config", None)
        config_overrides = getattr(provider_config, "config", {}) if provider_config else {}

        safety_settings = merged_kwargs.get("safety_settings") or config_overrides.get("safety_settings")
        if not safety_settings:
            merged_kwargs["safety_settings"] = DEFAULT_GEMINI_SAFETY_SETTINGS

        system_instruction = merged_kwargs.get("system_instruction") or config_overrides.get("system_instruction")
        if not system_instruction:
            merged_kwargs["system_instruction"] = DEFAULT_GEMINI_SYSTEM_INSTRUCTION

        base_generation_overrides = config_overrides.get("generation_config_overrides")
        runtime_overrides = merged_kwargs.get("generation_config_overrides")
        merged_generation: Dict[str, Any] = {}

        if isinstance(base_generation_overrides, dict):
            merged_generation.update({k: v for k, v in base_generation_overrides.items() if v is not None})

        if isinstance(runtime_overrides, dict):
            merged_generation.update({k: v for k, v in runtime_overrides.items() if v is not None})

        if merged_generation:
            merged_kwargs["generation_config_overrides"] = merged_generation

        return merged_kwargs
