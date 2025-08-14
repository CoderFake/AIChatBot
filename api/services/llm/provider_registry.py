
from typing import Dict, Any, List

from config.settings import get_settings


class ProviderRegistry:
    """Registry of default providers sourced from Settings only"""

    def __init__(self):
        self._initialized = False
        self._provider_definitions: Dict[str, Dict[str, Any]] = {}

    def _ensure_initialized(self):
        """Lazy initialization"""
        if not self._initialized:
            self._provider_definitions = self._initialize_provider_definitions()
            self._initialized = True

    def _initialize_provider_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Build provider definitions from settings (single source of truth)."""
        settings = get_settings()
        providers_cfg = settings.llm_providers or {}

        result: Dict[str, Dict[str, Any]] = {}
        for key, cfg in providers_cfg.items():
            name = getattr(cfg, "name", None) or (cfg.get("name") if isinstance(cfg, dict) else None) or key
            models = getattr(cfg, "models", None) or (cfg.get("models") if isinstance(cfg, dict) else []) or []
            default_model = getattr(cfg, "default_model", None) or (cfg.get("default_model") if isinstance(cfg, dict) else "") or ""
            config = getattr(cfg, "config", None) or (cfg.get("config") if isinstance(cfg, dict) else {}) or {}
            description = ""

            result[key] = {
                "display_name": name,
                "description": description,
                "provider_config": config,
                "models": models,
                "default_model": default_model,
            }

        return result

    def get_all_providers(self) -> Dict[str, Dict[str, Any]]:
        """Get all provider definitions"""
        self._ensure_initialized()
        return self._provider_definitions.copy()

    def get_provider_definition(self, provider_name: str) -> Dict[str, Any]:
        """Get definition of provider"""
        self._ensure_initialized()
        return self._provider_definitions.get(provider_name, {})

    def get_available_models(self, provider_name: str) -> List[str]:
        """Get list of models of provider"""
        definition = self.get_provider_definition(provider_name)
        return definition.get("models", [])

    def get_default_model(self, provider_name: str) -> str:
        """Get default model of provider"""
        definition = self.get_provider_definition(provider_name)
        return definition.get("default_model", "")


provider_registry = ProviderRegistry() 