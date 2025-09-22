"""
LLM Provider Manager với streaming support
Insert or Update into Database if not exist
"""

from typing import Dict, List, Any, Optional, AsyncGenerator, Union
from abc import ABC, abstractmethod
import json
import asyncio

from services.dataclasses.llm import LLMResponse
from config.settings import get_settings, LLMProviderConfig
from utils.logging import get_logger
import httpx

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
    

    def __reduce__(self):
        """Support for pickle/msgpack serialization using reduce protocol"""
        state = {
            'provider_name': self.name,
            'config': {
                'name': self.config.name,
                'default_model': self.config.default_model,
                'config': getattr(self.config, 'config', {}),
                'enabled': getattr(self.config, 'enabled', True)
            },
            'api_keys': getattr(self, '_api_keys', []),
            'runtime_api_keys': getattr(self, '_runtime_api_keys', []),
            'initialized': self._initialized
        }
        return (self._recreate_provider, (state,))

    @classmethod
    def _recreate_provider(cls, state):
        """Recreate provider from serialized state"""
        from config.settings import LLMProviderConfig

        config_data = state['config']
        config = LLMProviderConfig(
            name=config_data['name'],
            default_model=config_data['default_model'],
            config=config_data.get('config', {}),
            enabled=config_data.get('enabled', True)
        )

        provider_class = cls._get_provider_class(state['provider_name'])
        provider = provider_class(config)

        provider.name = state['provider_name']
        provider._api_keys = state.get('api_keys', [])
        provider._runtime_api_keys = state.get('runtime_api_keys', [])
        provider._initialized = state.get('initialized', False)

        return provider

    @classmethod
    def _get_provider_class(cls, provider_name):
        """Get provider class by name"""
        from services.llm.provider_manager import LLMProviderManager
        return LLMProviderManager.PROVIDER_CLASSES.get(provider_name, cls)

    async def ainvoke(self, prompt: str, model: Optional[str] = None, **kwargs) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """Async invoke LLM - returns LLMResponse or AsyncGenerator based on markdown parameter"""

        if hasattr(self, '_runtime_api_keys') and self._runtime_api_keys:
            if 'api_keys' not in kwargs:
                kwargs['api_keys'] = self._runtime_api_keys

        return await self._invoke_llm(prompt, model, **kwargs)

    @abstractmethod
    async def _invoke_llm(self, prompt: str, model: Optional[str] = None, **kwargs) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """Internal LLM invocation - to be overridden by subclasses"""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check provider health"""
        pass

# -----------------------------------------------------------------------------
# GeminiProvider
# -----------------------------------------------------------------------------
class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider using the official SDK.

    Features
    - SAFETY FILTERS DISABLED - allows ALL content types
    - Streaming with async generator
    - JSON mode (response_mime_type)
    - Key rotation across multiple API keys
    """

    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self._client = None
        self._api_keys: List[str] = config.config.get("api_keys", []) or []
        self._current_key_index: int = 0
        self._safety_settings = None  # built in initialize()

    async def initialize(self) -> bool:
        try:
            # Import new google-genai SDK
            from google import genai  # noqa: F401
            from google.genai import types  # noqa: F401

            self._initialized = True
            logger.info(
                "Gemini provider initialized successfully with new google-genai SDK (API keys will be loaded at runtime)"
            )
            return True
        except ImportError as e:
            logger.error("Failed to import google.genai: %s", e)
            return False
        except Exception as e:
            logger.error("Failed to initialize Gemini provider: %s", e)
            return False

    def _should_stream(self, kwargs: Dict[str, Any]) -> bool:
        return bool(kwargs.get("markdown", False))

    # ------------------------ core invoke ------------------------
    async def _invoke_llm(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        if not self._initialized:
            raise RuntimeError("Gemini provider not initialized")

        import json
        from google import genai
        from google.genai import types

        print("*"*100)
        print(f"GeminiProvider invoke_llm: {prompt}")
        print("*"*100)

        model_name = model or self.config.default_model

        runtime_keys = kwargs.get("api_keys")
        if runtime_keys and isinstance(runtime_keys, list) and any(runtime_keys):
            keys = [k for k in runtime_keys if k]
            current_key_index = 0
        else:
            keys = self._api_keys
            current_key_index = self._current_key_index

        if not keys:
            raise RuntimeError("No API keys provided for Gemini at runtime")

        max_retries = len(keys)

        response_format = kwargs.get("response_format")
        temperature = kwargs.get("temperature", self.config.config.get("temperature"))
        top_p = kwargs.get("top_p", self.config.config.get("top_p"))
        top_k = kwargs.get("top_k", self.config.config.get("top_k"))
        max_tokens = kwargs.get(
            "max_tokens", self.config.config.get("max_tokens", 8192)
        )
        system_instruction = kwargs.get("system_instruction")

        json_mode = bool(
            response_format == "json_object" or kwargs.get("json_mode", False)
        )
        if json_mode:
            if not any(
                w in (prompt or "").lower() for w in ("json", "format", "response_format")
            ):
                prompt = f"{prompt}\n\nPlease respond in valid JSON format."

        if self._should_stream(kwargs):
            return self._stream_response(prompt, model_name, keys, temperature, top_p, top_k, max_tokens, system_instruction, json_mode)

        for attempt in range(max_retries):
            try:
                current_key = keys[current_key_index]

                client = genai.Client(api_key=current_key)

                # Create content
                contents = [
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=prompt),
                        ],
                    ),
                ]

                safety_settings = [
                    types.SafetySetting(
                        category="HARM_CATEGORY_HARASSMENT",
                        threshold="BLOCK_NONE"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_HATE_SPEECH",
                        threshold="BLOCK_NONE"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        threshold="BLOCK_NONE"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_DANGEROUS_CONTENT",
                        threshold="BLOCK_NONE"
                    ),
                ]

                generate_content_config = types.GenerateContentConfig(
                    temperature=temperature if temperature is not None else None,
                    top_p=top_p if top_p is not None else None,
                    top_k=top_k if top_k is not None else None,
                    max_output_tokens=max_tokens,
                    response_mime_type="application/json" if json_mode else None,
                    safety_settings=safety_settings,
                )

                if system_instruction:
                    generate_content_config.system_instruction = system_instruction

                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=generate_content_config,
                    )

                    text = ""
                    if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                        for part in response.candidates[0].content.parts:
                            if hasattr(part, 'text') and part.text:
                                text += part.text

                    if not text:
                        logger.warning("Gemini returned empty response")
                        raise RuntimeError("Gemini returned empty response")

                    content = text
                    if json_mode:
                        try:
                            json.loads(content)
                        except json.JSONDecodeError:
                            content = json.dumps({"response": content})

                    if not runtime_keys:
                        self._current_key_index = current_key_index
                        metadata_key_index = current_key_index
                    else:
                        metadata_key_index = current_key_index

                    return LLMResponse(
                        content=content,
                        model=model_name,
                        provider="gemini",
                        usage=getattr(response, "usage_metadata", None),
                        metadata={"api_key_index": metadata_key_index},
                    )

                except Exception as e:
                    logger.warning("Gemini API call failed with key %d: %s", current_key_index, e)
                    current_key_index = (current_key_index + 1) % len(keys)
                    if attempt == max_retries - 1:
                        raise RuntimeError(f"All Gemini API keys failed: {e}")

            except Exception as e:
                logger.warning("Gemini API call failed with key %d: %s", current_key_index, e)
                current_key_index = (current_key_index + 1) % len(keys)
                if attempt == max_retries - 1:
                    raise RuntimeError(f"All Gemini API keys failed: {e}")

        raise RuntimeError("Gemini provider exhausted all retry attempts")

    def _is_safety_block(self, finish_reason: Any) -> bool:
        return False

    def _is_recitation_block(self, finish_reason: Any) -> bool:
        if finish_reason is None:
            return False
        if isinstance(finish_reason, (int,)):
            return finish_reason == 3
        s = str(finish_reason).upper()
        return "RECITATION" in s

    async def _stream_response(
        self,
        prompt: str,
        model_name: str,
        keys: List[str],
        temperature: float,
        top_p: float,
        top_k: int,
        max_tokens: int,
        system_instruction: str,
        json_mode: bool,
    ) -> AsyncGenerator[str, None]:
        from google import genai
        from google.genai import types

        current_key_index = 0
        current_key = keys[current_key_index]

        client = genai.Client(api_key=current_key)

        # Create content
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                ],
            ),
        ]

        # Create config with permissive safety settings
        safety_settings = [
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="BLOCK_NONE"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="BLOCK_NONE"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="BLOCK_NONE"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_NONE"
            ),
        ]

        generate_content_config = types.GenerateContentConfig(
            temperature=temperature if temperature is not None else None,
            top_p=top_p if top_p is not None else None,
            top_k=top_k if top_k is not None else None,
            max_output_tokens=max_tokens,
            response_mime_type="application/json" if json_mode else None,
            safety_settings=safety_settings,
        )

        if system_instruction:
            generate_content_config.system_instruction = system_instruction

        try:
            # Use streaming call
            for chunk in client.models.generate_content_stream(
                model=model_name,
                contents=contents,
                config=generate_content_config,
            ):
                if (
                    chunk.candidates is None
                    or chunk.candidates[0].content is None
                    or chunk.candidates[0].content.parts is None
                ):
                    continue

                for part in chunk.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                        yield part.text
        except Exception as e:
            logger.error("Gemini streaming failed: %s", e)
            raise RuntimeError(f"Gemini streaming error: {e}")

    async def cleanup(self) -> None:
        try:
            self._client = None
            logger.debug("Gemini provider connections cleaned up")
        except Exception as e:
            logger.debug("Error during Gemini cleanup: %s", e)

    async def health_check(self) -> bool:
        try:
            resp = await self.ainvoke("Health check ping", model=self.config.default_model)
            if isinstance(resp, LLMResponse):
                return bool(resp.content)
            return False
        except Exception:
            return False


class OllamaProvider(BaseLLMProvider):
    """Ollama provider with JSON response support"""
    
    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        base_url = config.config.get("base_url") or "http://ollama:11434"
        if base_url == "http://ollama:11434":
            base_url = "http://host.docker.internal:11434"
        if not base_url.startswith(("http://", "https://")):
            base_url = f"http://{base_url}"
        self._base_url = base_url.rstrip("/")
        self._available_models: List[str] = []
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize Ollama provider"""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                if resp.status_code != 200:
                    raise RuntimeError(f"Ollama API returned status {resp.status_code}")
                data = resp.json()
                self._available_models = [
                    m.get("name") for m in data.get("models", []) if m.get("name")
                ]
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Ollama provider: {e}")
            return False

    async def _invoke_llm(self, prompt: str, model: Optional[str] = None, **kwargs) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """Invoke Ollama with streaming support based on markdown parameter"""
        if not self._initialized:
            raise RuntimeError("Ollama provider not initialized")

        model_name = model or self.config.default_model
        if self._available_models and model_name not in self._available_models:
            raise ValueError(f"Model {model_name} not available in Ollama")

        options = {}
        options["temperature"] = kwargs.get("temperature", 0.7)
        options["num_predict"] = kwargs.get("max_tokens", 2048)
        
        for k in ("top_p", "top_k", "min_p", "seed", "stop",
                  "mirostat", "mirostat_eta", "mirostat_tau",
                  "repeat_last_n", "repeat_penalty", "num_ctx"):
            if k in kwargs and kwargs[k] is not None:
                options[k] = kwargs[k]

        response_format = kwargs.get("response_format")
        markdown = kwargs.get("markdown", False)
        
        if response_format == "json_object" or kwargs.get("json_mode", False):
            if not any(word in prompt.lower() for word in ["json", "format", "response_format"]):
                prompt = f"{prompt}\n\nPlease respond in valid JSON format."

        for param in ("system", "template", "context", "keep_alive", "images"):
            if kwargs.get(param) is not None:
                kwargs[param] = kwargs[param]

        if markdown:
            return self._stream_response(prompt, model_name, options, response_format, kwargs)
        
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": options
        }
        
        if response_format == "json_object" or kwargs.get("json_mode", False):
            payload["format"] = "json"

        for param in ("system", "template", "context", "keep_alive", "images"):
            if param in kwargs and kwargs[param] is not None:
                payload[param] = kwargs[param]

        timeout = float(self.config.config.get("timeout", 120))

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(f"{self._base_url}/api/generate", json=payload)
        except httpx.ConnectError as e:
            raise RuntimeError(f"Cannot connect to Ollama at {self._base_url}") from e
        except httpx.ReadTimeout as e:
            raise RuntimeError(f"Ollama request timed out after {timeout}s") from e
        except httpx.HTTPError as e:
            raise RuntimeError(f"HTTP error calling Ollama: {e}") from e

        if resp.status_code != 200:
            if resp.status_code == 404:
                raise RuntimeError(f"Ollama model '{model_name}' not found")
            if resp.status_code == 422:
                raise RuntimeError(f"Validation error: {resp.text}")
            if resp.status_code >= 500:
                raise RuntimeError(f"Ollama server error {resp.status_code}: {resp.text}")
            raise RuntimeError(f"Ollama API error {resp.status_code}: {resp.text}")

        data = resp.json()
        content = data.get("response", "")

        if payload.get("format") == "json" and isinstance(content, str):
            try:
                json.loads(content)
            except json.JSONDecodeError:
                content = json.dumps({"response": content})

        usage = {
            "prompt_eval_count": data.get("prompt_eval_count", 0),
            "eval_count": data.get("eval_count", 0),
        }

        metadata = {
            "base_url": self._base_url,
            "done": data.get("done", True),
            "done_reason": data.get("done_reason"),
            "total_duration": data.get("total_duration"),
            "load_duration": data.get("load_duration"),
            "prompt_eval_duration": data.get("prompt_eval_duration"),
            "eval_duration": data.get("eval_duration"),
            "context": data.get("context"),
        }

        return LLMResponse(
            content=content,
            model=model_name,
            provider="ollama",
            usage=usage,
            metadata=metadata,
        )

    async def _stream_response(self, prompt: str, model_name: str, options: Dict, response_format: str, extra_params: Dict) -> AsyncGenerator[str, None]:
        """Stream Ollama response chunks"""
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": True,
            "options": options
        }
        
        if response_format == "json_object" or extra_params.get("json_mode", False):
            payload["format"] = "json"

        for param in ("system", "template", "context", "keep_alive", "images"):
            if param in extra_params and extra_params[param] is not None:
                payload[param] = extra_params[param]

        timeout = float(self.config.config.get("timeout", 120))

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", f"{self._base_url}/api/generate", json=payload) as resp:
                    if resp.status_code != 200:
                        raise RuntimeError(f"Ollama streaming error {resp.status_code}: {await resp.aread()}")
                    
                    async for line in resp.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                chunk_text = data.get("response", "")
                                if chunk_text:
                                    yield chunk_text
                                if data.get("done", False):
                                    break
                            except json.JSONDecodeError:
                                continue

        except httpx.ConnectError as e:
            raise RuntimeError(f"Cannot connect to Ollama at {self._base_url}") from e
        except httpx.ReadTimeout as e:
            raise RuntimeError(f"Ollama streaming timed out after {timeout}s") from e
        except httpx.HTTPError as e:
            raise RuntimeError(f"HTTP error during Ollama streaming: {e}") from e

    async def health_check(self) -> bool:
        """Check Ollama health"""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider using official SDK with JSON mode"""
    
    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self._client = None
        self._api_keys = config.config.get("api_keys", [])
        self._current_key_index = 0
        self._base_url = config.config.get("base_url", "https://api.openai.com/v1")
    
    async def initialize(self) -> bool:
        """Initialize OpenAI provider"""
        try:
            if self._api_keys:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(
                    api_key=self._api_keys[0],
                    base_url=self._base_url
                )
            
            self._initialized = True
            logger.info(f"OpenAI provider initialized with {len(self._api_keys)} API keys")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI provider: {e}")
            return False
    
    async def _invoke_llm(self, prompt: str, model: Optional[str] = None, **kwargs) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """Invoke OpenAI API with streaming support based on markdown parameter"""
        if not self._initialized:
            raise RuntimeError("OpenAI provider not initialized")
        
        from openai import AsyncOpenAI
        
        model_name = model or self.config.default_model
        runtime_keys = kwargs.get("api_keys")
        if runtime_keys and isinstance(runtime_keys, list) and any(runtime_keys):
            keys = [k for k in runtime_keys if k]
            current_key_index = 0  # Reset index for runtime keys
        else:
            keys = self._api_keys
            current_key_index = self._current_key_index
        
        if not keys:
            raise RuntimeError("No API keys provided for OpenAI at runtime")
        max_retries = len(keys)
        
        temperature = kwargs.get("temperature")
        markdown = kwargs.get("markdown", False)
        
        if markdown:
            return self._stream_response(prompt, model_name, keys, temperature, kwargs)
        
        for attempt in range(max_retries):
            try:
                current_key = keys[current_key_index]
                client = AsyncOpenAI(
                    api_key=current_key,
                    base_url=self._base_url
                )
                
                request_params = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": kwargs.get("max_tokens", self.config.config.get("max_tokens", 4096))
                }
                
                response_format = kwargs.get("response_format")
                if response_format == "json_object" or kwargs.get("json_mode", False):
                    request_params["response_format"] = {"type": "json_object"}
                    if not any(word in prompt.lower() for word in ["json", "format", "response_format"]):
                        request_params["messages"][0]["content"] = f"{prompt}\n\nPlease respond in valid JSON format."
                
                response = await client.chat.completions.create(**request_params)
                content = response.choices[0].message.content
                
                # Update global index only if using instance keys  
                if runtime_keys:
                    metadata_key_index = current_key_index
                else:
                    self._current_key_index = current_key_index
                    metadata_key_index = current_key_index
                
                return LLMResponse(
                    content=content,
                    model=model_name,
                    provider="openai",
                    usage=response.usage.model_dump() if response.usage else None,
                    metadata={"api_key_index": metadata_key_index}
                )
                
            except Exception as e:
                logger.warning(f"OpenAI API call failed with key {current_key_index}: {e}")
                current_key_index = (current_key_index + 1) % len(keys)
                
                if attempt == max_retries - 1:
                    raise RuntimeError(f"All OpenAI API keys failed: {e}")
        
        raise RuntimeError("OpenAI provider exhausted all retry attempts")

    async def _stream_response(self, prompt: str, model_name: str, keys: List[str], temperature: float, kwargs: Dict) -> AsyncGenerator[str, None]:
        """Stream OpenAI response chunks"""
        from openai import AsyncOpenAI
        
        current_key_index = 0  # Always start from 0 for streaming
        current_key = keys[current_key_index]
        client = AsyncOpenAI(
            api_key=current_key,
            base_url=self._base_url
        )
        
        request_params = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": kwargs.get("max_tokens", self.config.config.get("max_tokens", 4096)),
            "stream": True
        }
        
        response_format = kwargs.get("response_format")
        if response_format == "json_object" or kwargs.get("json_mode", False):
            request_params["response_format"] = {"type": "json_object"}
            if not any(word in prompt.lower() for word in ["json", "format", "response_format"]):
                request_params["messages"][0]["content"] = f"{prompt}\n\nPlease respond in valid JSON format."
        
        try:
            stream = await client.chat.completions.create(**request_params)
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"OpenAI streaming failed: {e}")
            raise RuntimeError(f"OpenAI streaming error: {e}")
    
    async def health_check(self) -> bool:
        """Check OpenAI health"""
        try:
            response = await self.ainvoke("Test", model=self.config.default_model)
            if isinstance(response, LLMResponse):
                return response.content is not None
            return False
        except Exception:
            return False


class MistralProvider(BaseLLMProvider):
    """Mistral AI provider using official SDK"""
    
    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self._client = None
        self._api_keys = config.config.get("api_keys", [])
        self._current_key_index = 0
    
    async def initialize(self) -> bool:
        """Initialize Mistral provider"""
        try:
            if self._api_keys:
                from mistralai import Mistral

                self._client = Mistral(api_key=self._api_keys[0])
            
            self._initialized = True
            logger.info(f"Mistral provider initialized with {len(self._api_keys)} API keys")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Mistral provider: {e}")
            return False
    
    async def _invoke_llm(self, prompt: str, model: Optional[str] = None, **kwargs) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """Invoke Mistral API with streaming support based on markdown parameter"""
        if not self._initialized:
            raise RuntimeError("Mistral provider not initialized")
        
        from mistralai import Mistral
        
        model_name = model or self.config.default_model
        runtime_keys = kwargs.get("api_keys")
        if runtime_keys and isinstance(runtime_keys, list) and any(runtime_keys):
            keys = [k for k in runtime_keys if k]
            current_key_index = 0  # Reset index for runtime keys
        else:
            keys = self._api_keys
            current_key_index = self._current_key_index
        
        if not keys:
            raise RuntimeError("No API keys provided for Mistral at runtime")
        max_retries = len(keys)
        
        response_format = kwargs.get("response_format")
        markdown = kwargs.get("markdown", False)
        final_prompt = prompt
        if response_format == "json_object" or kwargs.get("json_mode", False):
            if not any(word in prompt.lower() for word in ["json", "format", "response_format"]):
                final_prompt = f"{prompt}\n\nPlease respond in valid JSON format."
        
        if markdown:
            return self._stream_response(final_prompt, model_name, keys, kwargs)
        
        for attempt in range(max_retries):
            try:
                current_key = keys[current_key_index]
                client = Mistral(api_key=current_key)
                
                response = await asyncio.wait_for(
                    client.chat.complete_async(
                        model=model_name,
                        messages=[{"role": "user", "content": final_prompt}],
                        temperature=kwargs.get("temperature", 0.7),
                        max_tokens=kwargs.get("max_tokens", self.config.config.get("max_tokens", 4096))
                    ),
                    timeout=120.0
                )
                
                content = response.choices[0].message.content
                
                if response_format == "json_object" or kwargs.get("json_mode", False):
                    try:
                        json.loads(content)
                    except json.JSONDecodeError:
                        content = json.dumps({"response": content})
                
                # Update global index only if using instance keys
                if runtime_keys:
                    metadata_key_index = current_key_index
                else:
                    self._current_key_index = current_key_index
                    metadata_key_index = current_key_index
                
                return LLMResponse(
                    content=content,
                    model=model_name,
                    provider="mistral",
                    usage=response.usage.model_dump() if response.usage else None,
                    metadata={"api_key_index": metadata_key_index}
                )
                
            except Exception as e:
                logger.warning(f"Mistral API call failed with key {current_key_index}: {e}")
                current_key_index = (current_key_index + 1) % len(keys)
                
                if attempt == max_retries - 1:
                    raise RuntimeError(f"All Mistral API keys failed: {e}")
        
        raise RuntimeError("Mistral provider exhausted all retry attempts")

    async def _stream_response(self, prompt: str, model_name: str, keys: List[str], kwargs: Dict) -> AsyncGenerator[str, None]:
        """Stream Mistral response chunks"""
        from mistralai import Mistral
        
        current_key_index = 0  # Always start from 0 for streaming
        current_key = keys[current_key_index]
        client = Mistral(api_key=current_key)
        
        try:
            stream = client.chat.stream(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", self.config.config.get("max_tokens", 4096))
            )
            
            for chunk in stream:
                if hasattr(chunk, 'data') and hasattr(chunk.data, 'choices') and chunk.data.choices:
                    delta_content = chunk.data.choices[0].delta.content
                    if delta_content:
                        yield delta_content
        except Exception as e:
            logger.error(f"Mistral streaming failed: {e}")
            raise RuntimeError(f"Mistral streaming error: {e}")
    
    async def health_check(self) -> bool:
        """Check Mistral health"""
        try:
            response = await self.ainvoke("Test", model=self.config.default_model)
            if isinstance(response, LLMResponse):
                return response.content is not None
            return False
        except Exception:
            return False


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider using official SDK"""
    
    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self._client = None
        self._api_keys = config.config.get("api_keys", [])
        self._current_key_index = 0
    
    async def initialize(self) -> bool:
        """Initialize Anthropic provider"""
        try:
            if self._api_keys:
                from anthropic import AsyncAnthropic

                self._client = AsyncAnthropic(api_key=self._api_keys[0])
            
            self._initialized = True
            logger.info(f"Anthropic provider initialized with {len(self._api_keys)} API keys")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic provider: {e}")
            return False
    
    async def _invoke_llm(self, prompt: str, model: Optional[str] = None, **kwargs) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """Invoke Anthropic Claude API with streaming support based on markdown parameter"""
        if not self._initialized:
            raise RuntimeError("Anthropic provider not initialized")
        
        from anthropic import AsyncAnthropic
        
        model_name = model or self.config.default_model
        runtime_keys = kwargs.get("api_keys")
        if runtime_keys and isinstance(runtime_keys, list) and any(runtime_keys):
            keys = [k for k in runtime_keys if k]
            current_key_index = 0  # Reset index for runtime keys
        else:
            keys = self._api_keys
            current_key_index = self._current_key_index
        
        if not keys:
            raise RuntimeError("No API keys provided for Anthropic at runtime")
        max_retries = len(keys)
        
        response_format = kwargs.get("response_format")
        markdown = kwargs.get("markdown", False)
        final_prompt = prompt
        if response_format == "json_object" or kwargs.get("json_mode", False):
            if not any(word in prompt.lower() for word in ["json", "format", "response_format"]):
                final_prompt = f"{prompt}\n\nPlease respond in valid JSON format only."
        
        if markdown:
            return self._stream_response(final_prompt, model_name, keys, kwargs)
        
        for attempt in range(max_retries):
            try:
                current_key = keys[current_key_index]
                client = AsyncAnthropic(api_key=current_key)
                
                response = await client.messages.create(
                    model=model_name,
                    max_tokens=kwargs.get("max_tokens", self.config.config.get("max_tokens", 4096)),
                    temperature=kwargs.get("temperature", 0.7),
                    messages=[{"role": "user", "content": final_prompt}]
                )
                
                content = response.content[0].text
                
                if response_format == "json_object" or kwargs.get("json_mode", False):
                    try:
                        json.loads(content)
                    except json.JSONDecodeError:
                        content = json.dumps({"response": content})
                
                # Update global index only if using instance keys
                if runtime_keys:
                    metadata_key_index = current_key_index
                else:
                    self._current_key_index = current_key_index
                    metadata_key_index = current_key_index
                
                return LLMResponse(
                    content=content,
                    model=model_name,
                    provider="anthropic",
                    usage=response.usage.model_dump() if response.usage else None,
                    metadata={"api_key_index": metadata_key_index}
                )
                
            except Exception as e:
                logger.warning(f"Anthropic API call failed with key {current_key_index}: {e}")
                current_key_index = (current_key_index + 1) % len(keys)
                
                if attempt == max_retries - 1:
                    raise RuntimeError(f"All Anthropic API keys failed: {e}")
        
        raise RuntimeError("Anthropic provider exhausted all retry attempts")

    async def _stream_response(self, prompt: str, model_name: str, keys: List[str], kwargs: Dict) -> AsyncGenerator[str, None]:
        """Stream Anthropic response chunks"""
        from anthropic import AsyncAnthropic
        
        current_key_index = 0  # Always start from 0 for streaming
        current_key = keys[current_key_index]
        client = AsyncAnthropic(api_key=current_key)
        
        try:
            async with client.messages.stream(
                model=model_name,
                max_tokens=kwargs.get("max_tokens", self.config.config.get("max_tokens", 4096)),
                temperature=kwargs.get("temperature", 0.7),
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        except Exception as e:
            logger.error(f"Anthropic streaming failed: {e}")
            raise RuntimeError(f"Anthropic streaming error: {e}")
    
    async def health_check(self) -> bool:
        """Check Anthropic health"""
        try:
            response = await self.ainvoke("Test", model=self.config.default_model)
            if isinstance(response, LLMResponse):
                return response.content is not None
            return False
        except Exception:
            return False


class LLMProviderManager:
    """Database-first LLM Provider Manager with Registry Fallback"""
    
    PROVIDER_CLASSES = {
        "gemini": GeminiProvider,
        "ollama": OllamaProvider,
        "openai": OpenAIProvider,
        "mistral": MistralProvider,
        "anthropic": AnthropicProvider
    }
    
    def __init__(self):
        self.settings = get_settings()
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize provider manager by loading and initializing all providers at startup"""
        if self._initialized:
            return

        for provider_name, provider_config in self.settings.llm_providers.items():
            if provider_config.enabled:
                try:
                    provider_class = self.PROVIDER_CLASSES.get(provider_name)
                    if provider_class:
                        provider = provider_class(provider_config)
                        success = await provider.initialize()
                        if success:
                            self._providers[provider_name] = provider
                            logger.info(f"Initialized provider: {provider_name}")
                        else:
                            logger.warning(f"Failed to initialize provider: {provider_name}")
                    else:
                        logger.warning(f"Unknown provider type: {provider_name}")
                except Exception as e:
                    logger.error(f"Failed to create/initialize provider {provider_name}: {e}")

        self._initialized = True
        logger.info(f"LLM Provider Manager initialized with {len(self._providers)} providers")

    
    def get_supported_providers(self) -> List[str]:
        """Get list of all supported provider types"""
        return list(self.PROVIDER_CLASSES.keys())
    
    
    async def get_provider(self, provider_name: Optional[str] = None) -> BaseLLMProvider:
        """Get LLM provider instance (all providers are lazy loaded at startup)"""
        if not self._initialized:
            await self.initialize()

        if not provider_name:
            enabled_providers = [name for name, config in self.settings.llm_providers.items() if config.enabled]
            if not enabled_providers:
                raise RuntimeError("No enabled LLM providers found in settings")
            provider_name = enabled_providers[0]

        if provider_name not in self._providers:
            raise RuntimeError(f"Provider {provider_name} not found. Available providers: {list(self._providers.keys())}")

        return self._providers[provider_name]
    
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