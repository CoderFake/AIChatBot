"""
Simplified LLM Provider Manager
Configuration-driven provider management
"""

from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass

from config.settings import get_settings, LLMProviderConfig
from utils.logging import get_logger

logger = get_logger(__name__)

@dataclass
class LLMResponse:
    """Standard LLM response wrapper"""
    content: str
    model: str
    provider: str
    usage: Dict[str, Any] = None
    metadata: Dict[str, Any] = None

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
            
            # Configure with first API key
            genai.configure(api_key=self._api_keys[0])
            
            # Test connection
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
    Simplified LLM Provider Manager
    Configuration-driven provider management
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize enabled providers"""
        if self._initialized:
            return
        
        try:
            enabled_providers = self.settings.get_enabled_providers()
            
            for provider_name in enabled_providers:
                await self._initialize_provider(provider_name)
            
            self._initialized = True
            logger.info(f"LLM Provider Manager initialized with {len(self._providers)} providers")
            
        except Exception as e:
            logger.error(f"Failed to initialize LLM Provider Manager: {e}")
            raise
    
    async def _initialize_provider(self, provider_name: str):
        """Initialize specific provider"""
        try:
            provider_config = self.settings.llm_providers.get(provider_name)
            
            if not provider_config or not provider_config.enabled:
                logger.info(f"Provider {provider_name} disabled")
                return
            
            # Create provider instance
            if provider_name == "gemini":
                provider = GeminiProvider(provider_config)
            elif provider_name == "ollama":
                provider = OllamaProvider(provider_config)
            elif provider_name == "mistral":
                provider = MistralProvider(provider_config)
            elif provider_name == "meta":
                provider = MetaProvider(provider_config)
            elif provider_name == "anthropic":
                provider = AnthropicProvider(provider_config)
            else:
                logger.warning(f"Unknown provider: {provider_name}")
                return
            
            # Initialize provider
            success = await provider.initialize()
            
            if success:
                self._providers[provider_name] = provider
                logger.info(f"Provider {provider_name} initialized successfully")
            else:
                logger.error(f"Failed to initialize provider {provider_name}")
                
        except Exception as e:
            logger.error(f"Error initializing provider {provider_name}: {e}")
    
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
    
    async def health_check_all(self) -> Dict[str, bool]:
        """Check health of all providers"""
        health_status = {}
        
        for provider_name, provider in self._providers.items():
            try:
                health_status[provider_name] = await provider.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {provider_name}: {e}")
                health_status[provider_name] = False
        
        return health_status
    
    def get_available_providers(self) -> List[str]:
        """Get list of available providers"""
        return list(self._providers.keys())


llm_provider_manager = LLMProviderManager()