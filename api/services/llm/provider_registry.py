
from typing import Dict, Any, List


class ProviderRegistry:
    """Registry of default providers""" 
    
    def __init__(self):
        self._initialized = False
        self._provider_definitions = {}
    
    def _ensure_initialized(self):
        """Lazy initialization"""
        if not self._initialized:
            self._provider_definitions = self._initialize_provider_definitions()
            self._initialized = True
    
    def _initialize_provider_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Define default providers"""
        return {
            "gemini": {
                "display_name": "Google Gemini",
                "description": "Google Gemini models for production use",
                "provider_config": {
                    "timeout": 60,
                    "max_retries": 3,
                    "api_keys": []  
                },
                "models": [
                    "gemini-2.0-flash",
                    "gemini-1.5-pro",
                    "gemini-1.5-flash"
                ],
                "default_model": "gemini-2.0-flash"
            },
            
            "ollama": {
                "display_name": "Ollama Local",
                "description": "Local Ollama server for development and testing",
                "provider_config": {
                    "base_url": "http://localhost:11434",
                    "timeout": 180,
                    "max_retries": 2
                },
                "models": [
                    "llama3.1:8b",
                    "llama3.1:70b",
                    "llama3.2:1b",
                    "llama3.2:3b",
                    "mistral-nemo:12b",
                    "qwen2.5:7b"
                ],
                "default_model": "llama3.1:8b"
            },
            
            "mistral": {
                "display_name": "Mistral AI",
                "description": "Mistral AI models for advanced reasoning",
                "provider_config": {
                    "base_url": "https://api.mistral.ai/v1",
                    "timeout": 90,
                    "max_retries": 3,
                    "api_keys": []  
                },
                "models": [
                    "mistral-large-latest",
                    "mistral-small-latest",
                    "pixtral-12b-2409",
                    "mistral-nemo-2407"
                ],
                "default_model": "mistral-large-latest"
            },
            
            "anthropic": {
                "display_name": "Anthropic Claude",
                "description": "Anthropic Claude models for reasoning and analysis",
                "provider_config": {
                    "base_url": "https://api.anthropic.com/v1",
                    "timeout": 120,
                    "max_retries": 3,
                    "api_keys": []
                },
                "models": [
                    "claude-3-5-sonnet-20241022",
                    "claude-3-5-haiku-20241022",
                    "claude-3-opus-20240229"
                ],
                "default_model": "claude-3-5-sonnet-20241022"
            }
        }
    
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