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
    
    @abstractmethod
    async def ainvoke(self, prompt: str, model: Optional[str] = None, **kwargs) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """Async invoke LLM - returns LLMResponse or AsyncGenerator based on markdown parameter"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check provider health"""
        pass


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider using official SDK"""

    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self._client = None
        self._api_keys = config.config.get("api_keys", [])
        self._current_key_index = 0
    
    async def initialize(self) -> bool:
        """Initialize Gemini provider"""
        try:
            if self._api_keys:
                import google.generativeai as genai
                
                genai.configure(api_key=self._api_keys[0])
                try:
                    test_model = genai.GenerativeModel(
                        model_name=self.config.default_model,
                        generation_config=genai.GenerationConfig(
                            response_mime_type="application/json",
                            response_schema={
                                "type": "object",
                                "properties": {
                                    "response": {"type": "string"}
                                }
                            }
                        )
                    )
                    
                    await asyncio.wait_for(
                        test_model.generate_content_async("Return JSON: {'response': 'test'}"),
                        timeout=10.0
                    )
                    logger.debug("Gemini provider test call successful")

                except Exception as e:
                    logger.warning(f"Gemini provider test call failed: {e} - proceeding anyway")

            self._initialized = True
            logger.info(f"Gemini provider initialized with {len(self._api_keys)} API keys")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Gemini provider: {e}")
            return False
    
    async def ainvoke(self, prompt: str, model: Optional[str] = None, **kwargs) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """Invoke Gemini API with streaming support based on markdown parameter"""
        if not self._initialized:
            raise RuntimeError("Gemini provider not initialized")
        
        import google.generativeai as genai
        
        model_name = model or self.config.default_model
        runtime_keys = kwargs.get("api_keys")
        if runtime_keys and isinstance(runtime_keys, list) and any(runtime_keys):
            keys = [k for k in runtime_keys if k]
        else:
            keys = self._api_keys
        if not keys:
            raise RuntimeError("No API keys provided for Gemini at runtime")
        max_retries = len(keys)
        
        response_format = kwargs.get("response_format")
        temperature = kwargs.get("temperature")
        markdown = kwargs.get("markdown", False)

        generation_config = {
            "max_output_tokens": kwargs.get("max_tokens", self.config.config.get("max_tokens", 8192)),
            "temperature": temperature,
        }
        
        if response_format == "json_object" or kwargs.get("json_mode", False):
            generation_config["response_mime_type"] = "application/json"
            if not any(word in prompt.lower() for word in ["json", "format", "response_format"]):
                prompt = f"{prompt}\n\nPlease respond in valid JSON format."
        
        if markdown:
            return self._stream_response(prompt, model_name, keys, generation_config)
        
        for attempt in range(max_retries):
            try:
                current_key = keys[self._current_key_index]
                genai.configure(api_key=current_key)
                
                llm_model = genai.GenerativeModel(
                    model_name=model_name,
                    generation_config=genai.GenerationConfig(**generation_config)
                )

                try:
                    response = await asyncio.wait_for(
                        llm_model.generate_content_async(prompt),
                        timeout=30.0
                    )
                    
                    content = response.text
                    
                    if response_format == "json_object" or kwargs.get("json_mode", False):
                        try:
                            json.loads(content)
                        except json.JSONDecodeError:
                            content = json.dumps({"response": content})
                    
                    return LLMResponse(
                        content=content,
                        model=model_name,
                        provider="gemini",
                        usage=getattr(response, "usage_metadata", None),
                        metadata={"api_key_index": self._current_key_index}
                    )

                except Exception as e:
                    error_msg = str(e).lower()
                    if 'protocol' in error_msg or 'grpc' in error_msg:
                        logger.debug(f"Suppressing gRPC internal error: {e}")
                        raise RuntimeError(f"Gemini API temporarily unavailable: {e}")
                    else:
                        raise

            except asyncio.TimeoutError:
                logger.warning(f"Gemini API call timeout with key {self._current_key_index}")
                self._current_key_index = (self._current_key_index + 1) % len(keys)

            except Exception as e:
                logger.warning(f"Gemini API call failed with key {self._current_key_index}: {e}")
                self._current_key_index = (self._current_key_index + 1) % len(keys)

                if attempt == max_retries - 1:
                    raise RuntimeError(f"All Gemini API keys failed: {e}")
        
        raise RuntimeError("Gemini provider exhausted all retry attempts")

    async def _stream_response(self, prompt: str, model_name: str, keys: List[str], generation_config: Dict) -> AsyncGenerator[str, None]:
        """Stream Gemini response chunks"""
        import google.generativeai as genai
        
        current_key = keys[self._current_key_index]
        genai.configure(api_key=current_key)
        
        llm_model = genai.GenerativeModel(
            model_name=model_name,
            generation_config=genai.GenerationConfig(**generation_config)
        )

        try:
            stream = await llm_model.generate_content_async(prompt, stream=True)
            async for chunk in stream:
                text = getattr(chunk, "text", None)
                if text:
                    yield text
        except Exception as e:
            logger.error(f"Gemini streaming failed: {e}")
            raise RuntimeError(f"Gemini streaming error: {e}")


    async def cleanup(self) -> None:
        """Cleanup gRPC connections"""
        try:
            import google.generativeai as genai
            genai.configure(api_key="")
            self._client = None
            logger.debug("Gemini provider connections cleaned up")
        except Exception as e:
            logger.debug(f"Error during Gemini cleanup: {e}")

    async def health_check(self) -> bool:
        """Check Gemini health"""
        try:
            response = await self.ainvoke("Test", model=self.config.default_model)
            if isinstance(response, LLMResponse):
                return response.content is not None
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
            print(f"Docker environment detected, using {base_url} for Ollama")
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

    async def ainvoke(self, prompt: str, model: Optional[str] = None, **kwargs) -> Union[LLMResponse, AsyncGenerator[str, None]]:
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

        # Nếu có tham số markdown, trả về streaming generator
        if markdown:
            return self._stream_response(prompt, model_name, options, response_format, kwargs)
        
        # Không có markdown, trả về LLMResponse như cũ
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
                
                try:
                    response = await self._client.chat.completions.create(
                        model=self.config.default_model,
                        messages=[{"role": "user", "content": "Test"}],
                        max_tokens=10
                    )
                    logger.debug("OpenAI provider test call successful")
                except Exception as e:
                    logger.warning(f"OpenAI provider test call failed: {e} - proceeding anyway")
            
            self._initialized = True
            logger.info(f"OpenAI provider initialized with {len(self._api_keys)} API keys")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI provider: {e}")
            return False
    
    async def ainvoke(self, prompt: str, model: Optional[str] = None, **kwargs) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """Invoke OpenAI API with streaming support based on markdown parameter"""
        if not self._initialized:
            raise RuntimeError("OpenAI provider not initialized")
        
        from openai import AsyncOpenAI
        
        model_name = model or self.config.default_model
        runtime_keys = kwargs.get("api_keys")
        if runtime_keys and isinstance(runtime_keys, list) and any(runtime_keys):
            keys = [k for k in runtime_keys if k]
        else:
            keys = self._api_keys
        if not keys:
            raise RuntimeError("No API keys provided for OpenAI at runtime")
        max_retries = len(keys)
        
        temperature = kwargs.get("temperature")
        markdown = kwargs.get("markdown", False)
        
        # Nếu có tham số markdown, trả về streaming generator
        if markdown:
            return self._stream_response(prompt, model_name, keys, temperature, kwargs)
        
        # Không có markdown, trả về LLMResponse như cũ
        for attempt in range(max_retries):
            try:
                current_key = keys[self._current_key_index]
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
                
                return LLMResponse(
                    content=content,
                    model=model_name,
                    provider="openai",
                    usage=response.usage.model_dump() if response.usage else None,
                    metadata={"api_key_index": self._current_key_index}
                )
                
            except Exception as e:
                logger.warning(f"OpenAI API call failed with key {self._current_key_index}: {e}")
                self._current_key_index = (self._current_key_index + 1) % len(keys)
                
                if attempt == max_retries - 1:
                    raise RuntimeError(f"All OpenAI API keys failed: {e}")
        
        raise RuntimeError("OpenAI provider exhausted all retry attempts")

    async def _stream_response(self, prompt: str, model_name: str, keys: List[str], temperature: float, kwargs: Dict) -> AsyncGenerator[str, None]:
        """Stream OpenAI response chunks"""
        from openai import AsyncOpenAI
        
        current_key = keys[self._current_key_index]
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
                
                try:
                    response = await asyncio.wait_for(
                        self._client.chat.complete_async(
                            model=self.config.default_model,
                            messages=[{"role": "user", "content": "Test"}],
                            max_tokens=10
                        ),
                        timeout=10.0
                    )
                    logger.debug("Mistral provider test call successful")
                except Exception as e:
                    logger.warning(f"Mistral provider test call failed: {e} - proceeding anyway")
            
            self._initialized = True
            logger.info(f"Mistral provider initialized with {len(self._api_keys)} API keys")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Mistral provider: {e}")
            return False
    
    async def ainvoke(self, prompt: str, model: Optional[str] = None, **kwargs) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """Invoke Mistral API with streaming support based on markdown parameter"""
        if not self._initialized:
            raise RuntimeError("Mistral provider not initialized")
        
        from mistralai import Mistral
        
        model_name = model or self.config.default_model
        runtime_keys = kwargs.get("api_keys")
        if runtime_keys and isinstance(runtime_keys, list) and any(runtime_keys):
            keys = [k for k in runtime_keys if k]
        else:
            keys = self._api_keys
        if not keys:
            raise RuntimeError("No API keys provided for Mistral at runtime")
        max_retries = len(keys)
        
        response_format = kwargs.get("response_format")
        markdown = kwargs.get("markdown", False)
        final_prompt = prompt
        if response_format == "json_object" or kwargs.get("json_mode", False):
            if not any(word in prompt.lower() for word in ["json", "format", "response_format"]):
                final_prompt = f"{prompt}\n\nPlease respond in valid JSON format."
        
        # Nếu có tham số markdown, trả về streaming generator
        if markdown:
            return self._stream_response(final_prompt, model_name, keys, kwargs)
        
        # Không có markdown, trả về LLMResponse như cũ
        for attempt in range(max_retries):
            try:
                current_key = keys[self._current_key_index]
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
                
                return LLMResponse(
                    content=content,
                    model=model_name,
                    provider="mistral",
                    usage=response.usage.model_dump() if response.usage else None,
                    metadata={"api_key_index": self._current_key_index}
                )
                
            except Exception as e:
                logger.warning(f"Mistral API call failed with key {self._current_key_index}: {e}")
                self._current_key_index = (self._current_key_index + 1) % len(keys)
                
                if attempt == max_retries - 1:
                    raise RuntimeError(f"All Mistral API keys failed: {e}")
        
        raise RuntimeError("Mistral provider exhausted all retry attempts")

    async def _stream_response(self, prompt: str, model_name: str, keys: List[str], kwargs: Dict) -> AsyncGenerator[str, None]:
        """Stream Mistral response chunks"""
        from mistralai import Mistral
        
        current_key = keys[self._current_key_index]
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
                
                try:
                    response = await self._client.messages.create(
                        model=self.config.default_model,
                        max_tokens=10,
                        messages=[{"role": "user", "content": "Test"}]
                    )
                    logger.debug("Anthropic provider test call successful")
                except Exception as e:
                    logger.warning(f"Anthropic provider test call failed: {e} - proceeding anyway")
            
            self._initialized = True
            logger.info(f"Anthropic provider initialized with {len(self._api_keys)} API keys")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Anthropic provider: {e}")
            return False
    
    async def ainvoke(self, prompt: str, model: Optional[str] = None, **kwargs) -> Union[LLMResponse, AsyncGenerator[str, None]]:
        """Invoke Anthropic Claude API with streaming support based on markdown parameter"""
        if not self._initialized:
            raise RuntimeError("Anthropic provider not initialized")
        
        from anthropic import AsyncAnthropic
        
        model_name = model or self.config.default_model
        runtime_keys = kwargs.get("api_keys")
        if runtime_keys and isinstance(runtime_keys, list) and any(runtime_keys):
            keys = [k for k in runtime_keys if k]
        else:
            keys = self._api_keys
        if not keys:
            raise RuntimeError("No API keys provided for Anthropic at runtime")
        max_retries = len(keys)
        
        response_format = kwargs.get("response_format")
        markdown = kwargs.get("markdown", False)
        final_prompt = prompt
        if response_format == "json_object" or kwargs.get("json_mode", False):
            if not any(word in prompt.lower() for word in ["json", "format", "response_format"]):
                final_prompt = f"{prompt}\n\nPlease respond in valid JSON format only."
        
        # Nếu có tham số markdown, trả về streaming generator
        if markdown:
            return self._stream_response(final_prompt, model_name, keys, kwargs)
        
        # Không có markdown, trả về LLMResponse như cũ
        for attempt in range(max_retries):
            try:
                current_key = keys[self._current_key_index]
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
                
                return LLMResponse(
                    content=content,
                    model=model_name,
                    provider="anthropic",
                    usage=response.usage.model_dump() if response.usage else None,
                    metadata={"api_key_index": self._current_key_index}
                )
                
            except Exception as e:
                logger.warning(f"Anthropic API call failed with key {self._current_key_index}: {e}")
                self._current_key_index = (self._current_key_index + 1) % len(keys)
                
                if attempt == max_retries - 1:
                    raise RuntimeError(f"All Anthropic API keys failed: {e}")
        
        raise RuntimeError("Anthropic provider exhausted all retry attempts")

    async def _stream_response(self, prompt: str, model_name: str, keys: List[str], kwargs: Dict) -> AsyncGenerator[str, None]:
        """Stream Anthropic response chunks"""
        from anthropic import AsyncAnthropic
        
        current_key = keys[self._current_key_index]
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
    
    def __init__(self, db_session=None):
        self.settings = get_settings()
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._initialized = False
        self._db_session = db_session
    
    async def initialize(self, db_session=None):
        """Initialize enabled providers - DATABASE-FIRST approach"""
        if self._initialized:
            return

        try:
            if db_session is not None:
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
            logger.info(f"LLM Provider Manager initialized with {initialized_count}/{len(provider_configs)} providers: {list(self._providers.keys())}")
            
        except Exception as e:
            logger.error(f"Failed to initialize LLM Provider Manager: {e}")
            raise
    
    async def _load_providers_from_database(self) -> Dict[str, Dict[str, Any]]:
        """Load provider configurations from database"""
        try:
            if not self._db_session:
                return {}
            
            from sqlalchemy import select
            from models.database.provider import Provider, ProviderModel
            
            result = await self._db_session.execute(
                select(Provider, ProviderModel)
                .join(ProviderModel, ProviderModel.provider_id == Provider.id, isouter=True)
            )
            rows = result.all()
            provider_map: Dict[str, Dict[str, Any]] = {}
            models_map: Dict[str, List[str]] = {}
            
            for provider, prov_model in rows:
                key = str(provider.id)
                if key not in provider_map:
                    provider_map[key] = {
                        "name": provider.provider_name,
                        "is_enabled": provider.is_enabled,
                        "config": provider.base_config or {},
                        "models": [],
                        "default_model": "",
                        "source": "database"
                    }
                    models_map[key] = []
                if prov_model and prov_model.model_name:
                    models_map[key].append(prov_model.model_name)
            
            provider_configs: Dict[str, Dict[str, Any]] = {}
            for key, pdata in provider_map.items():
                model_names = models_map.get(key, [])
                pdata["models"] = model_names
                default_model = ""
                if model_names:
                    default_model = model_names[0]
                pdata["default_model"] = default_model
                provider_configs[pdata["name"]] = pdata
            
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
                        **(settings_config.config if settings_config else {})
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
                logger.info(f"Provider {provider_name} initialized successfully ({source})")
                return True
            else:
                logger.error(f"Failed to initialize provider {provider_name}")
                return False
                
        except Exception as e:
            logger.error(f"Error initializing provider {provider_name}: {e}")
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


llm_provider_manager = None


async def get_llm_provider_for_tenant(tenant_id: str):
    """Get LLM provider for specific tenant based on WorkflowAgent configuration"""
    from services.cache.cache_manager import cache_manager
    
    cache_key = f"tenant_llm_provider:{tenant_id}"
    
    try:
        cached_provider_data = await cache_manager.get(cache_key)
        if cached_provider_data:
            logger.debug(f"Found cached provider data for tenant {tenant_id}")
            return await _create_provider_from_cache(cached_provider_data)
        
        logger.debug(f"No cached provider for tenant {tenant_id}, querying database")
        
        from config.database import get_db_context
        from models.database.agent import WorkflowAgent
        from models.database.provider import TenantProviderConfig, Provider
        from sqlalchemy import select
        import uuid

        async with get_db_context() as db_session:
            workflow_result = await db_session.execute(
                select(WorkflowAgent).where(
                    WorkflowAgent.tenant_id == uuid.UUID(tenant_id),
                    WorkflowAgent.is_active == True
                )
            )
            workflow_agent = workflow_result.scalar_one_or_none()

            if not workflow_agent:
                logger.warning(f"No active workflow agent found for tenant {tenant_id}")
                return None

            provider_result = await db_session.execute(
                select(TenantProviderConfig, Provider)
                .join(Provider, Provider.id == TenantProviderConfig.provider_id)
                .where(
                    TenantProviderConfig.tenant_id == uuid.UUID(tenant_id),
                    Provider.provider_name == workflow_agent.provider_name,
                    TenantProviderConfig.is_enabled == True
                )
            )
            provider_data = provider_result.first()

            if not provider_data:
                logger.warning(f"No enabled provider config found for {workflow_agent.provider_name} in tenant {tenant_id}")
                fallback_data = {
                    "provider_name": workflow_agent.provider_name,
                    "model_name": workflow_agent.model_name,
                    "model_config": workflow_agent.model_config or {},
                    "api_keys": [],
                    "base_config": {},
                    "is_fallback": True
                }
                await cache_manager.set(cache_key, fallback_data, ttl=1800)
                return await _get_fallback_provider(workflow_agent.provider_name)

            tenant_config, provider = provider_data

            provider_data_to_cache = {
                "provider_name": provider.provider_name,
                "model_name": workflow_agent.model_name,
                "model_config": workflow_agent.model_config or {},
                "api_keys": tenant_config.api_keys or [],
                "base_config": provider.base_config or {},
                "is_fallback": False
            }
            
            await cache_manager.set(cache_key, provider_data_to_cache, ttl=None)
            
            return await _create_provider_from_data(provider_data_to_cache)

    except Exception as e:
        logger.error(f"Failed to get LLM provider for tenant {tenant_id}: {e}")
        return None


async def _create_provider_from_cache(cached_data: dict):
    """Create provider instance from cached data"""
    return await _create_provider_from_data(cached_data)


async def _create_provider_from_data(provider_data: dict):
    """Create provider instance from provider data"""
    try:
        if provider_data.get("is_fallback"):
            return await _get_fallback_provider(provider_data["provider_name"])
            
        api_keys = provider_data.get("api_keys", [])
        if not api_keys:
            logger.error(f"No API keys provided for provider {provider_data.get('provider_name')}")
            return None

        provider_config = LLMProviderConfig(
            name=provider_data["provider_name"],
            enabled=True,
            models=[provider_data["model_name"]],
            default_model=provider_data["model_name"],
            config={
                **provider_data["model_config"],
                "api_keys": api_keys,
                "base_url": provider_data["base_config"].get("base_url"),
                "timeout": provider_data["base_config"].get("timeout", 120),
            }
        )

        provider_class = LLMProviderManager.PROVIDER_CLASSES.get(provider_data["provider_name"])
        if not provider_class:
            logger.error(f"Unknown provider type: {provider_data['provider_name']}")
            return None

        llm_provider = provider_class(provider_config)
        success = await llm_provider.initialize()

        if success:
            logger.info(f"Successfully created LLM provider {provider_data['provider_name']}")
            return llm_provider
        else:
            logger.error(f"Failed to initialize provider {provider_data['provider_name']}")
            if hasattr(llm_provider, 'cleanup'):
                try:
                    await llm_provider.cleanup()
                except Exception as cleanup_error:
                    logger.debug(f"Error during provider cleanup: {cleanup_error}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to create provider from data: {e}")
        try:
            if 'llm_provider' in locals() and llm_provider and hasattr(llm_provider, 'cleanup'):
                await llm_provider.cleanup()
        except Exception as cleanup_error:
            logger.debug(f"Error during provider cleanup on exception: {cleanup_error}")
        return None


async def _get_fallback_provider(provider_name: str):
    """Get fallback provider from settings when tenant config is not available"""
    try:
        settings = get_settings()
        provider_config = settings.llm_providers.get(provider_name)
        
        if not provider_config or not provider_config.enabled:
            logger.warning(f"Fallback provider {provider_name} not available or disabled")
            return None

        provider_class = LLMProviderManager.PROVIDER_CLASSES.get(provider_name)
        if not provider_class:
            logger.error(f"Unknown fallback provider type: {provider_name}")
            return None

        provider = provider_class(provider_config)
        success = await provider.initialize()
        
        if success:
            logger.info(f"Using fallback provider {provider_name}")
            return provider
        else:
            logger.error(f"Failed to initialize fallback provider {provider_name}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to get fallback provider {provider_name}: {e}")
        return None