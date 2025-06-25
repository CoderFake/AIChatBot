import asyncio
from typing import Dict, List, Optional, Any, Union
import random
from dataclasses import dataclass
from abc import ABC, abstractmethod
import time
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from config.settings import get_settings
from core.exceptions import LLMProviderError, ExternalServiceError
from utils.logging import get_logger, log_performance

logger = get_logger(__name__)
settings = get_settings()

@dataclass
class LLMUsageStats:
    """Statistics cho LLM usage"""
    provider: str
    model: str
    requests_count: int = 0
    tokens_used: int = 0
    avg_response_time: float = 0.0
    error_count: int = 0
    last_used: Optional[str] = None

class BaseLLMProvider(ABC):
    """Base class cho tất cả LLM providers"""
    
    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        self.is_initialized = False
        self.usage_stats = {}
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize provider với configuration từ admin"""
        pass
    
    @abstractmethod
    async def ainvoke(self, prompt: str, model: Optional[str] = None, **kwargs) -> Any:
        """Async invoke LLM"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check provider health"""
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[str]:
        """Get list of available models"""
        pass
    
    async def get_usage_stats(self, model: str) -> LLMUsageStats:
        """Get usage statistics cho model"""
        return self.usage_stats.get(model, LLMUsageStats(
            provider=self.provider_name,
            model=model
        ))

class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider"""
    
    def __init__(self):
        super().__init__("gemini")
        self.client = None
        self.api_keys = []
        self.current_key_index = 0
        self.available_models = [
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-pro"
        ]
    
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize Gemini provider"""
        try:
            import google.generativeai as genai
            
            self.api_keys = config.get("api_keys", [])
            if not self.api_keys:
                raise LLMProviderError("No Gemini API keys provided", provider="gemini")
            
            # Configure với first API key
            genai.configure(api_key=self.api_keys[0])
            
            # Test connection
            test_model = genai.GenerativeModel(config.get("default_model", "gemini-2.0-flash"))
            await test_model.generate_content_async("Hello")
            
            self.is_initialized = True
            logger.info(f"Gemini provider initialized with {len(self.api_keys)} API keys")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini provider: {e}")
            return False
    
    async def ainvoke(self, prompt: str, model: Optional[str] = None, **kwargs) -> Any:
        """Invoke Gemini API với key rotation"""
        if not self.is_initialized:
            raise LLMProviderError("Gemini provider not initialized", provider="gemini")
        
        import google.generativeai as genai
        
        model_name = model or settings.GEMINI_DEFAULT_MODEL
        max_retries = len(self.api_keys)
        
        for attempt in range(max_retries):
            try:
                # Use current API key
                current_key = self.api_keys[self.current_key_index]
                genai.configure(api_key=current_key)
                
                # Create model instance
                llm_model = genai.GenerativeModel(model_name)
                
                # Generate response
                response = await llm_model.generate_content_async(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=kwargs.get("max_tokens", settings.GEMINI_DEFAULT_MAX_TOKENS),
                        temperature=kwargs.get("temperature", 0.7),
                    )
                )
                
                # Update usage stats
                self._update_usage_stats(model_name, response)
                
                return response
                
            except Exception as e:
                logger.warning(f"Gemini API call failed with key {self.current_key_index}: {e}")
                
                # Rotate to next key
                self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
                
                if attempt == max_retries - 1:
                    raise LLMProviderError(f"All Gemini API keys failed: {e}", provider="gemini")
        
        raise LLMProviderError("Gemini provider exhausted all retry attempts", provider="gemini")
    
    async def health_check(self) -> bool:
        """Check Gemini health"""
        try:
            response = await self.ainvoke("Test", model="gemini-2.0-flash")
            return response is not None
        except:
            return False
    
    def get_available_models(self) -> List[str]:
        return self.available_models
    
    def _update_usage_stats(self, model: str, response) -> None:
        """Update usage statistics"""
        if model not in self.usage_stats:
            self.usage_stats[model] = LLMUsageStats(
                provider=self.provider_name,
                model=model
            )
        
        stats = self.usage_stats[model]
        stats.requests_count += 1
        
        # Extract token usage from response if available
        if hasattr(response, 'usage_metadata'):
            stats.tokens_used += getattr(response.usage_metadata, 'total_token_count', 0)

class OllamaProvider(BaseLLMProvider):
    """Ollama local LLM provider"""
    
    def __init__(self):
        super().__init__("ollama")
        self.base_url = None
        self.available_models = []
    
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize Ollama provider"""
        try:
            import httpx
            
            self.base_url = config.get("base_url", settings.OLLAMA_API_URL)
            
            # Test connection và get available models
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    models_data = response.json()
                    self.available_models = [model["name"] for model in models_data.get("models", [])]
                else:
                    raise Exception(f"Ollama API returned status {response.status_code}")
            
            self.is_initialized = True
            logger.info(f"Ollama provider initialized with {len(self.available_models)} models")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Ollama provider: {e}")
            return False
    
    async def ainvoke(self, prompt: str, model: Optional[str] = None, **kwargs) -> Any:
        """Invoke Ollama API"""
        if not self.is_initialized:
            raise LLMProviderError("Ollama provider not initialized", provider="ollama")
        
        import httpx
        
        model_name = model or settings.OLLAMA_DEFAULT_MODEL
        
        if model_name not in self.available_models:
            raise LLMProviderError(f"Model {model_name} not available in Ollama", provider="ollama")
        
        try:
            async with httpx.AsyncClient(timeout=settings.OLLAMA_TIMEOUT) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
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
                    
                    # Create response object similar to other providers
                    class OllamaResponse:
                        def __init__(self, content: str):
                            self.content = content
                    
                    # Update usage stats
                    self._update_usage_stats(model_name, result)
                    
                    return OllamaResponse(result.get("response", ""))
                else:
                    raise Exception(f"Ollama API returned status {response.status_code}")
                    
        except Exception as e:
            raise LLMProviderError(f"Ollama API call failed: {e}", provider="ollama")
    
    async def health_check(self) -> bool:
        """Check Ollama health"""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except:
            return False
    
    def get_available_models(self) -> List[str]:
        return self.available_models
    
    def _update_usage_stats(self, model: str, response: Dict[str, Any]) -> None:
        """Update usage statistics"""
        if model not in self.usage_stats:
            self.usage_stats[model] = LLMUsageStats(
                provider=self.provider_name,
                model=model
            )
        
        stats = self.usage_stats[model]
        stats.requests_count += 1
        
        # Extract token usage từ Ollama response
        if "eval_count" in response:
            stats.tokens_used += response.get("eval_count", 0)

class MistralProvider(BaseLLMProvider):
    """Mistral AI provider"""
    
    def __init__(self):
        super().__init__("mistral")
        self.api_key = None
        self.available_models = [
            "mistral-large-latest",
            "mistral-medium-latest",
            "mistral-small-latest"
        ]
    
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize Mistral provider"""
        try:
            self.api_key = config.get("api_key")
            if not self.api_key:
                raise LLMProviderError("No Mistral API key provided", provider="mistral")
            
            # Test connection
            # (Implementation would test actual API call)
            
            self.is_initialized = True
            logger.info("Mistral provider initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Mistral provider: {e}")
            return False
    
    async def ainvoke(self, prompt: str, model: Optional[str] = None, **kwargs) -> Any:
        """Invoke Mistral API"""
        if not self.is_initialized:
            raise LLMProviderError("Mistral provider not initialized", provider="mistral")
        
        # Implementation cho Mistral API call
        # (This would be implemented with actual Mistral SDK/API)
        
        raise NotImplementedError("Mistral provider implementation pending")
    
    async def health_check(self) -> bool:
        return self.is_initialized
    
    def get_available_models(self) -> List[str]:
        return self.available_models

class MetaProvider(BaseLLMProvider):
    """Meta Llama provider thông qua Ollama hoặc Together AI"""
    
    def __init__(self):
        super().__init__("meta")
        self.api_key = None
        self.base_url = None
        self.client = None
        self.available_models = [
            "llama-3.3-70b-instruct",
            "llama-3.2-90b-vision-instruct", 
            "llama-3.2-11b-vision-instruct",
            "llama-3.2-3b-instruct",
            "llama-3.2-1b-instruct",
            "llama-3.1-405b-instruct",
            "llama-3.1-70b-instruct",
            "llama-3.1-8b-instruct"
        ]
    
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize Meta provider"""
        try:
            # Check if using Ollama local setup
            self.use_ollama = config.get("use_ollama", False)
            
            if self.use_ollama:
                # Initialize Ollama client
                self.base_url = config.get("ollama_base_url", "http://localhost:11434")
                from langchain_ollama import ChatOllama
                self.client = ChatOllama(
                    base_url=self.base_url,
                    model=config.get("model", "llama3.1:8b"),
                    temperature=config.get("temperature", 0.1)
                )
            else:
                # Initialize Together AI client for Meta models
                self.api_key = config.get("api_key")
                if not self.api_key:
                    raise ValueError("Meta provider requires api_key for Together AI")
                
                self.base_url = config.get("base_url", "https://api.together.xyz/v1")
                
                # Import langchain-openai if available
                try:
                    from langchain_openai import ChatOpenAI
                    self.client = ChatOpenAI(
                        api_key=self.api_key,
                        base_url=self.base_url,
                        model=config.get("model", "meta-llama/Llama-3-8b-chat-hf"),
                        temperature=config.get("temperature", 0.1)
                    )
                except ImportError:
                    raise ImportError("langchain-openai required for Meta Together API")
            
            self.model = config.get("model", "llama3.1:8b")
            self.temperature = config.get("temperature", 0.1)
            self.max_tokens = config.get("max_tokens", 4096)
            
            self.health_status = "healthy"
            self.last_health_check = datetime.now()
            
            logger.info(f"Meta provider initialized successfully ({'Ollama' if self.use_ollama else 'Together AI'})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Meta provider: {e}")
            self.health_status = f"initialization_failed: {str(e)}"
            return False
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """Generate response using Meta Llama model"""
        if not self.client:
            raise RuntimeError("Meta provider not initialized")
        
        try:
            # Convert messages to LangChain format
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
            
            lc_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "system":
                    lc_messages.append(SystemMessage(content=content))
                elif role == "user":
                    lc_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    lc_messages.append(AIMessage(content=content))
            
            # Generate response
            start_time = time.time()
            
            if self.use_ollama:
                response = await self.client.ainvoke(lc_messages)
            else:
                response = await self.client.ainvoke(lc_messages)
            
            end_time = time.time()
            
            # Extract response content
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Update metrics
            self.total_requests += 1
            self.total_tokens += len(content.split())  # Rough token estimate
            self.last_request_time = datetime.now()
            
            return {
                "content": content,
                "model": self.model,
                "usage": {
                    "prompt_tokens": sum(len(msg.get("content", "").split()) for msg in messages),
                    "completion_tokens": len(content.split()),
                    "total_tokens": sum(len(msg.get("content", "").split()) for msg in messages) + len(content.split())
                },
                "response_time": end_time - start_time,
                "provider": "meta"
            }
            
        except Exception as e:
            logger.error(f"Meta provider generation failed: {e}")
            self.error_count += 1
            raise RuntimeError(f"Meta generation failed: {str(e)}")
    
    async def generate_streaming_response(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Generate streaming response"""
        if not self.client:
            raise RuntimeError("Meta provider not initialized")
        
        try:
            # Convert messages to LangChain format
            from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
            
            lc_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "system":
                    lc_messages.append(SystemMessage(content=content))
                elif role == "user":
                    lc_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    lc_messages.append(AIMessage(content=content))
            
            # Stream response
            start_time = time.time()
            accumulated_content = ""
            
            async for chunk in self.client.astream(lc_messages):
                if hasattr(chunk, 'content') and chunk.content:
                    accumulated_content += chunk.content
                    
                    yield {
                        "content": chunk.content,
                        "delta": chunk.content,
                        "model": self.model,
                        "provider": "meta",
                        "type": "content"
                    }
            
            # Final metrics update
            end_time = time.time()
            self.total_requests += 1
            self.total_tokens += len(accumulated_content.split())
            self.last_request_time = datetime.now()
            
            yield {
                "type": "done",
                "model": self.model,
                "provider": "meta",
                "usage": {
                    "prompt_tokens": sum(len(msg.get("content", "").split()) for msg in messages),
                    "completion_tokens": len(accumulated_content.split()),
                    "total_tokens": sum(len(msg.get("content", "").split()) for msg in messages) + len(accumulated_content.split())
                },
                "response_time": end_time - start_time
            }
            
        except Exception as e:
            logger.error(f"Meta streaming failed: {e}")
            self.error_count += 1
            yield {
                "type": "error",
                "error": f"Meta streaming failed: {str(e)}",
                "provider": "meta"
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Meta provider health"""
        try:
            # Simple health check - try to generate a short response
            test_messages = [{"role": "user", "content": "Hello"}]
            
            start_time = time.time()
            response = await self.generate_response(test_messages)
            end_time = time.time()
            
            self.health_status = "healthy"
            self.last_health_check = datetime.now()
            
            return {
                "status": "healthy",
                "response_time": end_time - start_time,
                "model": self.model,
                "mode": "ollama" if self.use_ollama else "together_ai",
                "last_check": self.last_health_check.isoformat()
            }
            
        except Exception as e:
            self.health_status = f"unhealthy: {str(e)}"
            self.last_health_check = datetime.now()
            
            return {
                "status": "unhealthy",
                "error": str(e),
                "model": self.model,
                "mode": "ollama" if self.use_ollama else "together_ai",
                "last_check": self.last_health_check.isoformat()
            }
    
    def get_available_models(self) -> List[str]:
        """Get list of available Meta models"""
        if self.use_ollama:
            # For Ollama, return common Llama models
            return [
                "llama3.1:8b",
                "llama3.1:70b", 
                "llama3.2:3b",
                "llama3.2:1b",
                "codellama:7b",
                "codellama:13b"
            ]
        else:
            # For Together AI, return full list
            return self.available_models

class LLMProviderManager:
    """
    Manager cho tất cả LLM providers
    Configuration được load từ admin settings
    """
    
    def __init__(self):
        self.providers: Dict[str, BaseLLMProvider] = {}
        self.initialized = False
        self.load_balancing_strategy = "round_robin"  # round_robin, random, performance
        self.provider_weights = {}
    
    async def initialize(self):
        """Initialize tất cả enabled providers từ admin config"""
        try:
            logger.info("Initializing LLM Provider Manager...")
            
            # Initialize providers based on admin settings
            enabled_providers = settings.enabled_providers
            
            for provider_name in enabled_providers:
                await self._initialize_provider(provider_name)
            
            self.initialized = True
            logger.info(f"LLM Provider Manager initialized với {len(self.providers)} providers")
            
        except Exception as e:
            logger.error(f"Failed to initialize LLM Provider Manager: {e}")
            raise
    
    async def _initialize_provider(self, provider_name: str):
        """Initialize specific provider"""
        try:
            provider_config = settings.get_provider_config(provider_name)
            
            if not provider_config.get("enabled", False):
                logger.info(f"Provider {provider_name} disabled by admin")
                return
            
            # Create provider instance
            if provider_name == "gemini":
                provider = GeminiProvider()
            elif provider_name == "ollama":
                provider = OllamaProvider()
            elif provider_name == "mistral":
                provider = MistralProvider()
            elif provider_name == "meta":
                provider = MetaProvider()
            # Add more providers as needed
            else:
                logger.warning(f"Unknown provider: {provider_name}")
                return
            
            # Initialize provider
            success = await provider.initialize(provider_config)
            
            if success:
                self.providers[provider_name] = provider
                logger.info(f"Provider {provider_name} initialized successfully")
            else:
                logger.error(f"Failed to initialize provider {provider_name}")
                
        except Exception as e:
            logger.error(f"Error initializing provider {provider_name}: {e}")
    
    async def get_llm(
        self, 
        provider: Optional[str] = None, 
        model: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        Get LLM instance based on admin configuration
        Auto-selects provider if not specified
        """
        if not self.initialized:
            raise LLMProviderError("LLM Provider Manager not initialized")
        
        if not self.providers:
            raise LLMProviderError("No LLM providers available")
        
        # Select provider
        selected_provider_name = provider or self._select_provider()
        
        if selected_provider_name not in self.providers:
            raise LLMProviderError(f"Provider {selected_provider_name} not available")
        
        selected_provider = self.providers[selected_provider_name]
        
        # Return wrapper that includes provider context
        return LLMWrapper(selected_provider, model, **kwargs)
    
    def _select_provider(self) -> str:
        """Select provider based on load balancing strategy"""
        available_providers = list(self.providers.keys())
        
        if not available_providers:
            raise LLMProviderError("No providers available")
        
        if self.load_balancing_strategy == "random":
            return random.choice(available_providers)
        elif self.load_balancing_strategy == "round_robin":
            # Simple round robin (in real implementation, would track state)
            return available_providers[0]
        elif self.load_balancing_strategy == "performance":
            # Select based on performance metrics
            return self._select_best_performance_provider(available_providers)
        else:
            return available_providers[0]
    
    def _select_best_performance_provider(self, providers: List[str]) -> str:
        """Select provider based on performance metrics"""
        best_provider = providers[0]
        best_score = 0
        
        for provider_name in providers:
            provider = self.providers[provider_name]
            # Calculate score based on response time, error rate, etc.
            score = self._calculate_provider_score(provider)
            
            if score > best_score:
                best_score = score
                best_provider = provider_name
        
        return best_provider
    
    def _calculate_provider_score(self, provider: BaseLLMProvider) -> float:
        """Calculate provider performance score"""
        # Implementation would consider:
        # - Average response time
        # - Error rate
        # - Availability
        # - Cost (if applicable)
        return 1.0  # Placeholder
    
    async def health_check_all(self) -> Dict[str, bool]:
        """Check health của tất cả providers"""
        health_status = {}
        
        for provider_name, provider in self.providers.items():
            try:
                health_status[provider_name] = await provider.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {provider_name}: {e}")
                health_status[provider_name] = False
        
        return health_status
    
    async def get_usage_statistics(self) -> Dict[str, Any]:
        """Get usage statistics cho tất cả providers"""
        stats = {}
        
        for provider_name, provider in self.providers.items():
            provider_stats = {}
            for model in provider.get_available_models():
                model_stats = await provider.get_usage_stats(model)
                provider_stats[model] = {
                    "requests_count": model_stats.requests_count,
                    "tokens_used": model_stats.tokens_used,
                    "avg_response_time": model_stats.avg_response_time,
                    "error_count": model_stats.error_count,
                    "last_used": model_stats.last_used
                }
            stats[provider_name] = provider_stats
        
        return stats
    
    def get_available_models(self) -> Dict[str, List[str]]:
        """Get all available models từ tất cả providers"""
        models = {}
        for provider_name, provider in self.providers.items():
            models[provider_name] = provider.get_available_models()
        return models

class LLMWrapper:
    """Wrapper cho LLM calls với additional functionality"""
    
    def __init__(self, provider: BaseLLMProvider, model: Optional[str] = None, **kwargs):
        self.provider = provider
        self.model = model
        self.kwargs = kwargs
    
    async def ainvoke(self, prompt: str, **additional_kwargs) -> Any:
        """Async invoke với error handling và retry logic"""
        merged_kwargs = {**self.kwargs, **additional_kwargs}
        
        try:
            return await self.provider.ainvoke(prompt, self.model, **merged_kwargs)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise LLMProviderError(f"LLM invocation failed: {e}", provider=self.provider.provider_name)

# Global instance
llm_provider_manager = LLMProviderManager() 