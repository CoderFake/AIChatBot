"""
LLM Provider Manager
Insert or Update into Database if not exist
"""

from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod

from services.dataclasses.llm import LLMResponse
from config.settings import get_settings, LLMProviderConfig
from utils.logging import get_logger

logger = get_logger(__name__)


class BaseLLMProvider(ABC):
    """Base class for LLM providers"""
    
    def __init__(self, config: LLMProviderConfig):
        self.config = config
        self.name = config.name
        self._initialized = False
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize provider"""
        pass
    
    @abstractmethod
    async def ainvoke(self, prompt: str, model: Optional[str] = None, **kwargs) -> LLMResponse:
        """Async invoke LLM"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check provider health"""
        pass

class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider"""
    
    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self._client = None
        self._api_keys = config.config.get("api_keys", [])
        self._current_key_index = 0
    
    async def initialize(self) -> bool:
        """Initialize Gemini provider"""
        try:
            if not self._api_keys:
                logger.error("No Gemini API keys provided")
                return False
            
            import google.generativeai as genai
            
            genai.configure(api_key=self._api_keys[0])
            
            test_model = genai.GenerativeModel(self.config.default_model)
            await test_model.generate_content_async("Hello")
            
            self._initialized = True
            logger.info(f"Gemini provider initialized with {len(self._api_keys)} API keys")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini provider: {e}")
            return False
    
    async def ainvoke(self, prompt: str, model: Optional[str] = None, **kwargs) -> LLMResponse:
        """Invoke Gemini API with key rotation"""
        if not self._initialized:
            raise RuntimeError("Gemini provider not initialized")
        
        import google.generativeai as genai
        
        model_name = model or self.config.default_model
        max_retries = len(self._api_keys)
        
        for attempt in range(max_retries):
            try:
                # Use current API key
                current_key = self._api_keys[self._current_key_index]
                genai.configure(api_key=current_key)
                
                # Create model instance
                llm_model = genai.GenerativeModel(model_name)
                
                # Generate response
                response = await llm_model.generate_content_async(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=kwargs.get("max_tokens", self.config.config.get("max_tokens", 8192)),
                        temperature=kwargs.get("temperature", 0.7),
                    )
                )
                
                return LLMResponse(
                    content=response.text,
                    model=model_name,
                    provider="gemini",
                    usage=getattr(response, "usage_metadata", None),
                    metadata={"api_key_index": self._current_key_index}
                )
                
            except Exception as e:
                logger.warning(f"Gemini API call failed with key {self._current_key_index}: {e}")
                
                # Rotate to next key
                self._current_key_index = (self._current_key_index + 1) % len(self._api_keys)
                
                if attempt == max_retries - 1:
                    raise RuntimeError(f"All Gemini API keys failed: {e}")
        
        raise RuntimeError("Gemini provider exhausted all retry attempts")
    
    async def health_check(self) -> bool:
        """Check Gemini health"""
        try:
            response = await self.ainvoke("Test", model=self.config.default_model)
            return response.content is not None
        except Exception:
            return False

class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider"""
    
    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self._base_url = config.config.get("base_url")
        self._available_models = []
    
    async def initialize(self) -> bool:
        """Initialize Ollama provider"""
        try:
            import httpx
            
            # Test connection and get available models
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self._base_url}/api/tags")
                if response.status_code == 200:
                    models_data = response.json()
                    self._available_models = [model["name"] for model in models_data.get("models", [])]
                else:
                    raise Exception(f"Ollama API returned status {response.status_code}")
            
            self._initialized = True
            logger.info(f"Ollama provider initialized with {len(self._available_models)} models")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Ollama provider: {e}")
            return False
    
    async def ainvoke(self, prompt: str, model: Optional[str] = None, **kwargs) -> LLMResponse:
        """Invoke Ollama API"""
        if not self._initialized:
            raise RuntimeError("Ollama provider not initialized")
        
        import httpx
        
        model_name = model or self.config.default_model
        
        if model_name not in self._available_models:
            raise ValueError(f"Model {model_name} not available in Ollama")
        
        try:
            timeout = self.config.config.get("timeout", 120)
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": kwargs.get("temperature", 0.7),
                            "num_predict": kwargs.get("max_tokens", 2048),
                        }
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    return LLMResponse(
                        content=result.get("response", ""),
                        model=model_name,
                        provider="ollama",
                        usage={"eval_count": result.get("eval_count", 0)},
                        metadata={"base_url": self._base_url}
                    )
                else:
                    raise Exception(f"Ollama API returned status {response.status_code}")
                    
        except Exception as e:
            raise RuntimeError(f"Ollama API call failed: {e}")
    
    async def health_check(self) -> bool:
        """Check Ollama health"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self._base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False

class MistralProvider(BaseLLMProvider):
    """Mistral AI provider"""
    
    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self._api_keys = config.config.get("api_keys", [])
        self._current_key_index = 0
        self._base_url = config.config.get("base_url", "https://api.mistral.ai/v1")
    
    async def initialize(self) -> bool:
        """Initialize Mistral provider"""
        try:
            if not self._api_keys:
                logger.error("No Mistral API keys provided")
                return False
            
            import httpx
            
            headers = {
                "Authorization": f"Bearer {self._api_keys[0]}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self._base_url}/models", headers=headers)
                if response.status_code != 200:
                    raise Exception(f"Mistral API test failed: {response.status_code}")
            
            self._initialized = True
            logger.info(f"Mistral provider initialized with {len(self._api_keys)} API keys")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Mistral provider: {e}")
            return False
    
    async def ainvoke(self, prompt: str, model: Optional[str] = None, **kwargs) -> LLMResponse:
        """Invoke Mistral API with key rotation"""
        if not self._initialized:
            raise RuntimeError("Mistral provider not initialized")
        
        import httpx
        
        model_name = model or self.config.default_model
        max_retries = len(self._api_keys)
        
        for attempt in range(max_retries):
            try:
                current_key = self._api_keys[self._current_key_index]
                headers = {
                    "Authorization": f"Bearer {current_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", self.config.config.get("max_tokens", 4096))
                }
                
                async with httpx.AsyncClient(timeout=120) as client:
                    response = await client.post(
                        f"{self._base_url}/chat/completions",
                        headers=headers,
                        json=payload
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        content = result["choices"][0]["message"]["content"]
                        
                        return LLMResponse(
                            content=content,
                            model=model_name,
                            provider="mistral",
                            usage=result.get("usage"),
                            metadata={"api_key_index": self._current_key_index}
                        )
                    else:
                        raise Exception(f"Mistral API returned status {response.status_code}: {response.text}")
                
            except Exception as e:
                logger.warning(f"Mistral API call failed with key {self._current_key_index}: {e}")
                
                self._current_key_index = (self._current_key_index + 1) % len(self._api_keys)
                
                if attempt == max_retries - 1:
                    raise RuntimeError(f"All Mistral API keys failed: {e}")
        
        raise RuntimeError("Mistral provider exhausted all retry attempts")
    
    async def health_check(self) -> bool:
        """Check Mistral health"""
        try:
            response = await self.ainvoke("Hello", model=self.config.default_model)
            return response.content is not None
        except Exception:
            return False

class MetaProvider(BaseLLMProvider):
    """Meta Llama provider via Together AI"""
    
    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self._api_keys = config.config.get("api_keys", [])
        self._current_key_index = 0
        self._base_url = config.config.get("base_url", "https://api.together.xyz/v1")
    
    async def initialize(self) -> bool:
        """Initialize Meta provider"""
        try:
            if not self._api_keys:
                logger.error("No Meta/Together API keys provided")
                return False
            
            import httpx
            
            headers = {
                "Authorization": f"Bearer {self._api_keys[0]}",
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self._base_url}/models", headers=headers)
                if response.status_code != 200:
                    raise Exception(f"Meta/Together API test failed: {response.status_code}")
            
            self._initialized = True
            logger.info(f"Meta provider initialized with {len(self._api_keys)} API keys")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Meta provider: {e}")
            return False
    
    async def ainvoke(self, prompt: str, model: Optional[str] = None, **kwargs) -> LLMResponse:
        """Invoke Meta Llama via Together AI with key rotation"""
        if not self._initialized:
            raise RuntimeError("Meta provider not initialized")
        
        import httpx
        
        model_name = model or self.config.default_model
        max_retries = len(self._api_keys)
        
        for attempt in range(max_retries):
            try:
                current_key = self._api_keys[self._current_key_index]
                headers = {
                    "Authorization": f"Bearer {current_key}",
                    "Content-Type": "application/json"
                }
                
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", self.config.config.get("max_tokens", 4096))
                }
                
                async with httpx.AsyncClient(timeout=120) as client:
                    response = await client.post(
                        f"{self._base_url}/chat/completions",
                        headers=headers,
                        json=payload
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        content = result["choices"][0]["message"]["content"]
                        
                        return LLMResponse(
                            content=content,
                            model=model_name,
                            provider="meta",
                            usage=result.get("usage"),
                            metadata={"api_key_index": self._current_key_index}
                        )
                    else:
                        raise Exception(f"Meta API returned status {response.status_code}: {response.text}")
                
            except Exception as e:
                logger.warning(f"Meta API call failed with key {self._current_key_index}: {e}")
                
                # Rotate to next key
                self._current_key_index = (self._current_key_index + 1) % len(self._api_keys)
                
                if attempt == max_retries - 1:
                    raise RuntimeError(f"All Meta API keys failed: {e}")
        
        raise RuntimeError("Meta provider exhausted all retry attempts")
    
    async def health_check(self) -> bool:
        """Check Meta health"""
        try:
            response = await self.ainvoke("Hello", model=self.config.default_model)
            return response.content is not None
        except Exception:
            return False

class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider"""
    
    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self._api_keys = config.config.get("api_keys", [])
        self._current_key_index = 0
        self._base_url = config.config.get("base_url", "https://api.anthropic.com/v1")
    
    async def initialize(self) -> bool:
        """Initialize Anthropic provider"""
        try:
            if not self._api_keys:
                logger.error("No Anthropic API keys provided")
                return False
            
            # Test connection with first API key
            import httpx
            
            headers = {
                "x-api-key": self._api_keys[0],
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }
            
            # Test with a simple request
            payload = {
                "model": self.config.default_model,
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Hello"}]
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base_url}/messages",
                    headers=headers,
                    json=payload
                )
                if response.status_code not in [200, 201]:
                    raise Exception(f"Anthropic API test failed: {response.status_code}")
            
            self._initialized = True
            logger.info(f"Anthropic provider initialized with {len(self._api_keys)} API keys")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic provider: {e}")
            return False
    
    async def ainvoke(self, prompt: str, model: Optional[str] = None, **kwargs) -> LLMResponse:
        """Invoke Anthropic Claude API with key rotation"""
        if not self._initialized:
            raise RuntimeError("Anthropic provider not initialized")
        
        import httpx
        
        model_name = model or self.config.default_model
        max_retries = len(self._api_keys)
        
        for attempt in range(max_retries):
            try:
                # Use current API key
                current_key = self._api_keys[self._current_key_index]
                headers = {
                    "x-api-key": current_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                }
                
                # Prepare request payload
                payload = {
                    "model": model_name,
                    "max_tokens": kwargs.get("max_tokens", self.config.config.get("max_tokens", 4096)),
                    "temperature": kwargs.get("temperature", 0.7),
                    "messages": [{"role": "user", "content": prompt}]
                }
                
                async with httpx.AsyncClient(timeout=120) as client:
                    response = await client.post(
                        f"{self._base_url}/messages",
                        headers=headers,
                        json=payload
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        content = result["content"][0]["text"]
                        
                        return LLMResponse(
                            content=content,
                            model=model_name,
                            provider="anthropic",
                            usage=result.get("usage"),
                            metadata={"api_key_index": self._current_key_index}
                        )
                    else:
                        raise Exception(f"Anthropic API returned status {response.status_code}: {response.text}")
                
            except Exception as e:
                logger.warning(f"Anthropic API call failed with key {self._current_key_index}: {e}")
                
                # Rotate to next key
                self._current_key_index = (self._current_key_index + 1) % len(self._api_keys)
                
                if attempt == max_retries - 1:
                    raise RuntimeError(f"All Anthropic API keys failed: {e}")
        
        raise RuntimeError("Anthropic provider exhausted all retry attempts")

class LLMProviderManager:
    """
    Database-first LLM Provider Manager with Registry Fallback
    """
    
    PROVIDER_CLASSES = {
        "gemini": GeminiProvider,
        "ollama": OllamaProvider,
        "mistral": MistralProvider,
        "meta": MetaProvider,
        "anthropic": AnthropicProvider
    }
    
    def __init__(self):
        self.settings = get_settings()
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._initialized = False
        self._db_session = None
    
    async def initialize(self, db_session=None):
        """Initialize enabled providers - DATABASE-FIRST approach"""
        if self._initialized:
            return
        
        try:
            self._db_session = db_session
            
            provider_configs = await self._load_providers_from_database()
            
            if not provider_configs:
                logger.warning("No providers in database, using registry fallback")
                provider_configs = await self._load_providers_from_registry_fallback()
            
            logger.info(f"Found {len(provider_configs)} provider configurations")
            
            initialized_count = 0
            for provider_name, config in provider_configs.items():
                if config.get("is_enabled", False):
                    success = await self._initialize_provider(provider_name, config)
                    if success:
                        initialized_count += 1
            
            self._initialized = True
            logger.info(f"✅ LLM Provider Manager initialized with {initialized_count}/{len(provider_configs)} providers: {list(self._providers.keys())}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize LLM Provider Manager: {e}")
            raise
    
    async def _load_providers_from_database(self) -> Dict[str, Dict[str, Any]]:
        """Load provider configurations from database"""
        try:
            if not self._db_session:
                return {}
            
            from models.database import Provider
            
            db_providers = self._db_session.query(Provider).all()
            provider_configs = {}
            
            for db_provider in db_providers:
                provider_configs[db_provider.name] = {
                    "name": db_provider.name,
                    "display_name": db_provider.display_name,
                    "description": db_provider.description,
                    "is_enabled": db_provider.is_enabled,
                    "models": db_provider.models or [],
                    "default_model": db_provider.default_model,
                    "config": db_provider.provider_config or {},
                    "source": "database"
                }
            
            logger.info(f"Loaded {len(provider_configs)} providers from database")
            return provider_configs
            
        except Exception as e:
            logger.error(f"Failed to load providers from database: {e}")
            return {}
    
    async def _load_providers_from_registry_fallback(self) -> Dict[str, Dict[str, Any]]:
        """Fallback: Load providers from registry + settings"""
        try:
            from services.llm.provider_registry import provider_registry
            
            registry_providers = provider_registry.get_all_providers()
            provider_configs = {}
            
            for provider_name, registry_def in registry_providers.items():
                settings_config = self.settings.llm_providers.get(provider_name)
                is_enabled = settings_config and settings_config.enabled if settings_config else False
                
                provider_configs[provider_name] = {
                    "name": provider_name,
                    "display_name": registry_def["display_name"],
                    "description": registry_def["description"],
                    "is_enabled": is_enabled,
                    "models": registry_def["models"],
                    "default_model": registry_def["default_model"],
                    "config": {
                        **registry_def["provider_config"],
                        "api_keys": settings_config.config.get("api_keys", []) if settings_config else []
                    },
                    "source": "registry_fallback"
                }
            
            logger.warning(f"Loaded {len(provider_configs)} providers from registry fallback")
            return provider_configs
            
        except Exception as e:
            logger.error(f"Registry fallback failed: {e}")
            return {}
    
    def _convert_to_llm_provider_config(self, config: Dict[str, Any]) -> LLMProviderConfig:
        """Convert config dict to LLMProviderConfig"""
        return LLMProviderConfig(
            name=config["name"],
            enabled=config.get("is_enabled", False),
            models=config.get("models", []),
            default_model=config.get("default_model", ""),
            config=config.get("config", {})
        )
    
    async def _initialize_provider(self, provider_name: str, config: Dict[str, Any] = None) -> bool:
        """Initialize specific provider from config"""
        try:
            if config is None:
                provider_config = self.settings.llm_providers.get(provider_name)
                if not provider_config or not provider_config.enabled:
                    logger.info(f"Provider {provider_name} disabled or not configured")
                    return False
                llm_config = provider_config
            else:
                if not config.get("is_enabled", False):
                    logger.info(f"Provider {provider_name} is disabled")
                    return False
                llm_config = self._convert_to_llm_provider_config(config)
            
            provider_class = self.PROVIDER_CLASSES.get(provider_name)
            if not provider_class:
                logger.warning(f"Unknown provider type: {provider_name}. Available: {list(self.PROVIDER_CLASSES.keys())}")
                return False
            
            provider = provider_class(llm_config)
            
            success = await provider.initialize()
            
            if success:
                self._providers[provider_name] = provider
                source = config.get("source", "settings") if config else "settings"
                logger.info(f"✅ Provider {provider_name} initialized successfully ({source})")
                return True
            else:
                logger.error(f"❌ Failed to initialize provider {provider_name}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error initializing provider {provider_name}: {e}")
            return False
    
    def get_supported_providers(self) -> List[str]:
        """Get list of all supported provider types"""
        return list(self.PROVIDER_CLASSES.keys())
    
    def validate_provider_configs(self) -> Dict[str, List[str]]:
        """Validate all provider configurations"""
        validation_results = {}
        
        for provider_name, provider_config in self.settings.llm_providers.items():
            issues = []
            
            if provider_name not in self.PROVIDER_CLASSES:
                issues.append(f"Unsupported provider type: {provider_name}")
            
            config = provider_config.config
            if provider_name in ["gemini", "mistral", "meta", "anthropic"]:
                if not config.get("api_keys") or not any(key.strip() for key in config.get("api_keys", [])):
                    issues.append(f"Missing or empty API keys")
            
            if provider_name == "ollama":
                if not config.get("base_url"):
                    issues.append("Missing base_url for Ollama")
            
            if not provider_config.models:
                issues.append("No models configured")
            
            if not provider_config.default_model:
                issues.append("No default model specified")
            
            validation_results[provider_name] = issues
        
        return validation_results
    
    async def get_provider(self, provider_name: Optional[str] = None) -> BaseLLMProvider:
        """Get LLM provider instance"""
        if not self._initialized:
            await self.initialize()
        
        if not self._providers:
            raise RuntimeError("No LLM providers available")
        
        if provider_name and provider_name in self._providers:
            return self._providers[provider_name]
        else:
            return next(iter(self._providers.values()))
    
    async def health_check_all(self) -> Dict[str, Dict[str, Any]]:
        """Check health of all providers with detailed status"""
        health_status = {}
        
        for provider_name, provider in self._providers.items():
            try:
                is_healthy = await provider.health_check()
                provider_config = self.settings.llm_providers.get(provider_name)
                
                health_status[provider_name] = {
                    "healthy": is_healthy,
                    "enabled": provider_config.enabled if provider_config else False,
                    "models": provider_config.models if provider_config else [],
                    "default_model": provider_config.default_model if provider_config else None
                }
            except Exception as e:
                logger.error(f"Health check failed for {provider_name}: {e}")
                health_status[provider_name] = {
                    "healthy": False,
                    "error": str(e),
                    "enabled": False
                }
        
        return health_status
    
    def get_available_providers(self) -> List[str]:
        """Get list of available (initialized) providers"""
        return list(self._providers.keys())
    
    def get_provider_summary(self) -> Dict[str, Any]:
        """Get summary of all provider configurations"""
        return {
            "supported": self.get_supported_providers(),
            "configured": list(self.settings.llm_providers.keys()),
            "enabled": self.settings.get_enabled_providers(),
            "available": self.get_available_providers(),
            "validation": self.validate_provider_configs()
        }


llm_provider_manager = LLMProviderManager()