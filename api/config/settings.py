"""
Centralized configuration management cho Agentic RAG System
Loại bỏ hardcode, centralize tất cả settings
"""

from typing import Dict, Any, Optional, List, Union
import os
from functools import lru_cache
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

load_dotenv()

class DatabaseConfig(BaseModel):
    """Database configuration"""
    url: str = Field(default="postgresql://postgres:postgres@db-postgres:5432/newwave_chatbot")
    pool_size: int = Field(default=10)
    max_overflow: int = Field(default=20)
    pool_timeout: int = Field(default=30)
    pool_recycle: int = Field(default=3600)
    
    @property
    def async_url(self) -> str:
        return self.url.replace("postgresql://", "postgresql+asyncpg://")

class VectorConfig(BaseModel):
    """Vector database configuration"""
    host: str = Field(default="db-milvus")
    port: int = Field(default=19530)
    user: str = Field(default="milvus")
    password: str = Field(default="milvus")
    default_collection: str = Field(default="chatbot")

class CacheConfig(BaseModel):
    """Redis cache configuration"""
    host: str = Field(default="redis")
    port: int = Field(default=6379)
    password: Optional[str] = Field(default=None)
    db: int = Field(default=0)
    ttl: int = Field(default=3600)
    
    @property
    def url(self) -> str:
        auth_part = f":{self.password}@" if self.password else ""
        return f"redis://{auth_part}{self.host}:{self.port}/{self.db}"

class LLMProviderConfig(BaseModel):
    """LLM provider configuration"""
    name: str
    enabled: bool = Field(default=False)
    config: Dict[str, Any] = Field(default_factory=dict)
    models: List[str] = Field(default_factory=list)
    default_model: Optional[str] = Field(default=None)

class AgentConfig(BaseModel):
    """Agent configuration"""
    name: str
    enabled: bool = Field(default=True)
    domain: str
    capabilities: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    model: str = Field(default="gemini-2.0-flash")
    provider: str = Field(default="gemini") 
    confidence_threshold: float = Field(default=0.7)
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=8192)

class WorkflowConfig(BaseModel):
    """Workflow configuration"""
    max_iterations: int = Field(default=10)
    timeout_seconds: int = Field(default=300)
    enable_reflection: bool = Field(default=True)
    enable_semantic_routing: bool = Field(default=True)
    enable_document_grading: bool = Field(default=True)
    enable_citation_generation: bool = Field(default=True)
    enable_query_expansion: bool = Field(default=True)
    enable_hallucination_check: bool = Field(default=True)
    checkpointer_type: str = Field(default="redis")

class StorageConfig(BaseModel):
    """MinIO storage configuration"""
    endpoint: str = Field(default="localhost:9000")
    access_key: str = Field(default="minioadmin")
    secret_key: str = Field(default="minioadmin")
    secure: bool = Field(default=False)
    bucket_prefix: str = Field(default="agentic-rag")

class CollectionConfig(BaseModel):
    """Milvus collection configuration"""
    name: str
    description: str
    agent: str
    index_type: str = Field(default="HNSW")  
    metric_type: str = Field(default="COSINE")
    index_params: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = Field(default=True)

class Settings(BaseModel):
    """Main application settings"""
    
    # Basic App Configuration
    ENV: str = Field(default="dev")
    DEBUG: bool = Field(default=True)
    APP_NAME: str = Field(default="Agentic RAG API")
    APP_HOST: str = Field(default="0.0.0.0")
    APP_PORT: int = Field(default=8000)
    
    # Security
    SECRET_KEY: str = Field(default="secret_key_development_only")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    ALLOWED_HOSTS: List[str] = Field(default=["*"])
    CORS_ORIGINS: List[str] = Field(default=["*"])

    # OTP Settings
    OTP_SECRET_KEY: str = Field(default="your_secret_key_here")
    OTP_VALIDITY_SECONDS: int = Field(default=30)
    OTP_DIGITS: int = Field(default=8)
    OTP_TOLERANCE_WINDOWS: int = Field(default=2)
    
    # Infrastructure Configs
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    vector_db: VectorConfig = Field(default_factory=VectorConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    
    # LLM Providers - Configurable, not hardcoded
    llm_providers: Dict[str, LLMProviderConfig] = Field(default_factory=lambda: {
        "gemini": LLMProviderConfig(
            name="gemini",
            enabled=True,
            config={
                "api_keys": os.getenv("GEMINI_API_KEYS", "").split(","),
                "timeout": 60,
                "max_tokens": 8192,
                "temperature": 0.7
            },
            models=["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
            default_model="gemini-2.0-flash"
        ),
        "ollama": LLMProviderConfig(
            name="ollama",
            enabled=True,
            config={
                "base_url": os.getenv("OLLAMA_API_URL", "http://192.168.200.57:11434"),
                "timeout": 120,
                "temperature": 0.1
            },
            models=["llama3.1:8b", "llama3.1:70b", "llama3.2:3b"],
            default_model="llama3.1:8b"
        ),
        "mistral": LLMProviderConfig(
            name="mistral",
            enabled=False,
            config={
                "api_keys": os.getenv("MISTRAL_API_KEYS", "").split(",") if os.getenv("MISTRAL_API_KEYS") else [],
                "base_url": os.getenv("MISTRAL_API_URL", "https://api.mistral.ai/v1"),
                "timeout": 60,
                "temperature": 0.7,
                "max_tokens": 4096
            },
            models=["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest"],
            default_model="mistral-large-latest"
        ),
        "meta": LLMProviderConfig(
            name="meta",
            enabled=False,
            config={
                "api_keys": os.getenv("META_API_KEYS", "").split(",") if os.getenv("META_API_KEYS") else [],
                "base_url": os.getenv("META_API_URL", "https://api.together.xyz/v1"),
                "use_ollama": os.getenv("META_USE_OLLAMA", "false").lower() == "true",
                "timeout": 60,
                "temperature": 0.1
            },
            models=[
                "llama-3.3-70b-instruct", "llama-3.2-90b-vision-instruct",
                "llama-3.2-11b-vision-instruct", "llama-3.1-405b-instruct"
            ],
            default_model="llama-3.1-405b-instruct"
        ),
        "anthropic": LLMProviderConfig(
            name="anthropic",
            enabled=False,
            config={
                "api_keys": os.getenv("ANTHROPIC_API_KEYS", "").split(",") if os.getenv("ANTHROPIC_API_KEYS") else [],
                "base_url": os.getenv("ANTHROPIC_API_URL", "https://api.anthropic.com/v1"),
                "timeout": 120,
                "temperature": 0.7,
                "max_tokens": 4096
            },
            models=[
                "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", 
                "claude-3-opus-20240229", "claude-3-sonnet-20240229"
            ],
            default_model="claude-3-5-sonnet-20241022"
        )
    })
    
    # NO MORE HARDCODE AGENTS - Database-First approach
    # Agents configuration loaded from database via agent_service
    
    # Workflow Configuration
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    
    # Orchestrator Settings
    orchestrator: Dict[str, Any] = Field(default_factory=lambda: {
        "enabled": True,
        "model": "gemini-2.0-flash",
        "confidence_threshold": 0.7,
        "timeout": 30,
        "strategy": "llm_orchestrator",  # llm_orchestrator, keyword_matching, hybrid
        "max_agents_per_query": 3
    })
    
    # RAG Settings
    rag: Dict[str, Any] = Field(default_factory=lambda: {
        "default_top_k": 5,
        "default_threshold": 0.2,
        "max_tokens": 8192,
        "chunk_size": 512,
        "chunk_overlap": 128,
        "embedding_model": "BAAI/bge-m3",
        "embedding_dimensions": 1024,
        "embedding_device": "cpu"
    })
    
    languages: Dict[str, Dict[str, Any]] = Field(default_factory=lambda: {
        "vi": {
            "name": "Tiếng Việt",
            "code": "vi",
            "weekdays": {
                0: "Thứ Hai", 1: "Thứ Ba", 2: "Thứ Tư", 3: "Thứ Năm",
                4: "Thứ Sáu", 5: "Thứ Bảy", 6: "Chủ Nhật"
            },
            "unknown_text": "Không xác định"
        },
        "en": {
            "name": "English",
            "code": "en", 
            "weekdays": {
                0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
                4: "Friday", 5: "Saturday", 6: "Sunday"
            },
            "unknown_text": "Unknown"
        }
    })
    
    # File Processing
    file_processing: Dict[str, Any] = Field(default_factory=lambda: {
        "max_file_size_mb": 100,
        "allowed_types": [
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "text/markdown"
        ],
        "upload_dir": "/app/uploads",
        "processing_timeout": 300
    })
    
    # Performance & Monitoring
    performance: Dict[str, Any] = Field(default_factory=lambda: {
        "max_concurrent_requests": 100,
        "request_timeout": 60,
        "enable_performance_monitoring": True,
        "log_slow_queries": True,
        "slow_query_threshold": 1.0
    })
    
    @field_validator("ENV")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed_envs = ["dev", "stg", "prod"]
        if v not in allowed_envs:
            raise ValueError(f"ENV must be one of {allowed_envs}")
        return v
    
    def is_production(self) -> bool:
        return self.ENV == "prod"
    
    def is_development(self) -> bool:
        return self.ENV == "dev"
    
    def _get_tool_settings_from_registry(self) -> Dict[str, bool]:
        """Dynamic tool enablement from tool_registry + environment (DRY)"""
        try:
            from services.tools.tool_registry import tool_registry
            
            all_tools = tool_registry.get_all_tools()
            tool_settings = {}
            
            for tool_name, tool_def in all_tools.items():
                settings_key = tool_def.get("settings_key")
                if settings_key:
                    default_enabled = tool_def.get("default_enabled", True)
                    env_value = os.getenv(settings_key, str(default_enabled).lower())
                    tool_settings[tool_name] = env_value.lower() == "true"
                else:
                    tool_settings[tool_name] = True
            
            return tool_settings
            
        except Exception as e:
            return {}
    
    
    def get_enabled_providers(self) -> List[str]:
        return [name for name, config in self.llm_providers.items() if config.enabled]
    
    def get_enabled_agents(self) -> List[str]:
        """Simple: Get enabled agents (to be implemented with database later)"""
       
        return []
    
    def get_enabled_tools(self) -> List[str]:
        """Get list of tools enabled via environment variables (DRY)"""
        tool_settings = self._get_tool_settings_from_registry()
        return [tool_name for tool_name, enabled in tool_settings.items() if enabled]
    
    def get_agent_config(self, agent_name: str) -> Optional[Dict[str, Any]]:
       
        return None
    
    def get_tool_config(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get tool runtime configuration from tool_registry + environment (NO HARDCODE)"""
        try:
            from services.tools.tool_registry import tool_registry
            
            tool_def = tool_registry.get_tool_definition(tool_name)
            if not tool_def:
                return {}
                
            base_config = tool_def.get("tool_config", {})
            runtime_config = {}
            
            for key, default_value in base_config.items():
                env_key = f"{tool_name.upper()}_{key.upper()}"
                env_value = os.getenv(env_key)
                
                if env_value is not None:
                    if isinstance(default_value, int):
                        runtime_config[key] = int(env_value)
                    elif isinstance(default_value, float):
                        runtime_config[key] = float(env_value)
                    elif isinstance(default_value, bool):
                        runtime_config[key] = env_value.lower() == "true"
                    elif isinstance(default_value, list):
                        runtime_config[key] = env_value.split(",") if env_value else []
                    else:
                        runtime_config[key] = env_value
                else:
                    runtime_config[key] = default_value
                    
            return runtime_config
            
        except Exception as e:
            return {}
    
    def is_tool_enabled(self, tool_name: str) -> bool:
        """Check if a tool is enabled via environment variable (DRY)"""
        tool_settings = self._get_tool_settings_from_registry()
        return tool_settings.get(tool_name, False)
    
    def get_provider_config(self, provider_name: str) -> Optional[Dict[str, Any]]:
        provider = self.llm_providers.get(provider_name)
        return provider.config if provider else None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

def reload_settings() -> Settings:
    """Reload settings (clear cache)"""
    get_settings.cache_clear()
    return get_settings()