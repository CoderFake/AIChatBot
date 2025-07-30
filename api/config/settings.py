import os
from typing import Dict, List, Any, Optional
from functools import lru_cache

import torch
from pydantic import BaseSettings, Field, validator, root_validator
from pydantic.dataclasses import dataclass


@dataclass
class LLMProviderConfig:
    """Configuration for LLM providers"""
    name: str
    enabled: bool = False
    models: List[str] = Field(default_factory=list)
    default_model: str = ""
    config: Dict[str, Any] = Field(default_factory=dict)


@dataclass
class WorkflowConfig:
    """LangGraph workflow configuration"""
    max_iterations: int = 10
    timeout_seconds: int = 300
    enable_reflection: bool = True
    enable_semantic_routing: bool = True
    checkpointer_type: str = "memory"


@dataclass
class OrchestratorConfig:
    """Orchestrator configuration"""
    enabled: bool = True
    strategy: str = "llm_orchestrator"
    max_agents_per_query: int = 3
    confidence_threshold: float = 0.7
    conflict_resolution_enabled: bool = True


@dataclass
class MilvusConfig:
    """Milvus vector database configuration"""
    public_uri: str = "http://milvus_public:19530"
    private_uri: str = "http://milvus_private:19530"
    collection_prefix: str = "rag"
    vector_dim: int = 1024
    metric_type: str = "IP"
    index_type: str = "HNSW"
    index_params: Dict[str, Any] = Field(default_factory=lambda: {"M": 16, "efConstruction": 200})
    search_params: Dict[str, Any] = Field(default_factory=lambda: {"ef": 64})


@dataclass
class StorageConfig:
    """MinIO/S3 storage configuration"""
    endpoint: str = "minio:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    secure: bool = False
    bucket_prefix: str = "rag"


@dataclass
class EmbeddingConfig:
    """Embedding model configuration"""
    model_name: str = "BAAI/bge-m3"
    device: str = "cpu"
    batch_size: int = 12
    max_length: int = 8192
    use_fp16: bool = False


@dataclass
class TenantCacheConfig:
    """Tenant-specific cache configuration for Redis"""
    tenant_id: str
    
    def get_provider_cache_key(self) -> str:
        """Get Redis key for tenant providers cache"""
        return f"tenant:{self.tenant_id}:providers"
    
    def get_agent_cache_key(self) -> str:
        """Get Redis key for tenant agents cache"""
        return f"tenant:{self.tenant_id}:agents"
    
    def get_tool_cache_key(self) -> str:
        """Get Redis key for tenant tools cache"""
        return f"tenant:{self.tenant_id}:tools"
    
    def get_workflow_cache_key(self) -> str:
        """Get Redis key for tenant workflow config cache"""
        return f"tenant:{self.tenant_id}:workflows"
    
    def get_permission_cache_key(self) -> str:
        """Get Redis key for tenant permissions cache"""
        return f"tenant:{self.tenant_id}:permissions"


class Settings(BaseSettings):
    """Application settings with comprehensive configuration"""
    
    # Application
    APP_NAME: str = "Multi-Agent RAG System"
    APP_VERSION: str = "2.0.0"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    ENV: str = "development"
    DEBUG: bool = True
    TIMEZONE: str = "Asia/Ho_Chi_Minh"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/multi_agent_rag"
    
    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    
    # Milvus
    MILVUS_PUBLIC_HOST: str = "milvus_public"
    MILVUS_PUBLIC_PORT: int = 19530
    MILVUS_PRIVATE_HOST: str = "milvus_private" 
    MILVUS_PRIVATE_PORT: int = 19530
    MILVUS_COLLECTION_PREFIX: str = "rag"
    
    # Embedding
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIMENSIONS: int = 1024
    EMBEDDING_BATCH_SIZE: int = 12

    # Device
    DEVICE: str = "cpu"
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    
    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: List[str] = ["localhost:9092"]
    KAFKA_DOCUMENT_TOPIC: str = "document_processing"
    KAFKA_CONSUMER_GROUP: str = "document_processors"
    
    # Configuration Objects
    llm_providers: Dict[str, LLMProviderConfig] = Field(default_factory=dict)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    orchestrator: OrchestratorConfig = Field(default_factory=OrchestratorConfig)
    milvus: MilvusConfig = Field(default_factory=MilvusConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    
    @root_validator(pre=True)
    def update_configs_from_env(cls, values):
        """Update configuration objects from environment variables"""
        milvus_config = values.get('milvus', MilvusConfig())
        if values.get('MILVUS_PUBLIC_HOST') and values.get('MILVUS_PUBLIC_PORT'):
            milvus_config.public_uri = f"http://{values['MILVUS_PUBLIC_HOST']}:{values['MILVUS_PUBLIC_PORT']}"
        if values.get('MILVUS_PRIVATE_HOST') and values.get('MILVUS_PRIVATE_PORT'):
            milvus_config.private_uri = f"http://{values['MILVUS_PRIVATE_HOST']}:{values['MILVUS_PRIVATE_PORT']}"
        values['milvus'] = milvus_config
        
        embedding_config = values.get('embedding', EmbeddingConfig())
        if values.get('EMBEDDING_MODEL'):
            embedding_config.model_name = values['EMBEDDING_MODEL']
        if values.get('EMBEDDING_DIMENSIONS'):
            milvus_config.vector_dim = values['EMBEDDING_DIMENSIONS']
        if values.get('EMBEDDING_BATCH_SIZE'):
            embedding_config.batch_size = values['EMBEDDING_BATCH_SIZE']
        values['embedding'] = embedding_config
        
        return values
    
    @validator('llm_providers', pre=True, always=True)
    def setup_default_providers(cls, v):
        """Setup default LLM provider configurations (API keys loaded from tenant cache in Redis)"""
        if not v:
            v = {}
        
        default_providers = {
            "gemini": LLMProviderConfig(
                name="gemini",
                enabled=False,
                models=["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
                default_model="gemini-2.0-flash",
                config={
                    "timeout": 60,
                    "max_retries": 3
                }
            ),
            "ollama": LLMProviderConfig(
                name="ollama",
                enabled=False,
                models=["llama3.1:8b", "llama3.1:70b", "llama3.2:1b", "mistral-nemo:12b"],
                default_model="llama3.1:8b",
                config={
                    "base_url": "http://localhost:11434",
                    "timeout": 180,
                    "max_retries": 2
                }
            ),
            "anthropic": LLMProviderConfig(
                name="anthropic",
                enabled=False,
                models=["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
                default_model="claude-3-5-sonnet-20241022",
                config={
                    "base_url": "https://api.anthropic.com/v1",
                    "timeout": 120
                }
            ),
            "mistral": LLMProviderConfig(
                name="mistral",
                enabled=False,
                models=["mistral-large-latest", "mistral-small-latest"],
                default_model="mistral-large-latest",
                config={
                    "base_url": "https://api.mistral.ai/v1",
                    "timeout": 90
                }
            )
        }
        
        for provider_name, default_config in default_providers.items():
            if provider_name not in v:
                v[provider_name] = default_config
        
        return v
    
    @property
    def database_url(self) -> str:
        """Get database URL"""
        return self.DATABASE_URL
    
    @property
    def redis_url(self) -> str:
        """Get Redis URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @lru_cache(maxsize=1)
    def get_device(self) -> str:
        """Get computation device (CPU/GPU)"""
        if torch.cuda.is_available() and self.DEVICE != "cpu":
            return "cuda"
        return "cpu"
    
    def get_enabled_providers(self) -> List[str]:
        """Get list of enabled LLM providers (loaded from tenant cache at runtime)"""
        return [name for name, config in self.llm_providers.items() if config.enabled]
    
    def get_enabled_agents(self) -> Dict[str, Any]:
        """Get enabled agents (loaded from tenant cache at runtime)"""
        return {}
    
    def get_enabled_tools(self) -> Dict[str, Any]:
        """Get enabled tools (loaded from tenant cache at runtime)"""
        return {}
    
    def get_tenant_cache_config(self, tenant_id: str) -> TenantCacheConfig:
        """Get tenant-specific cache configuration"""
        return TenantCacheConfig(tenant_id=tenant_id)
    
    def get_cache_invalidation_pattern(self, tenant_id: str) -> str:
        """Get Redis pattern to invalidate all tenant cache"""
        return f"tenant:{tenant_id}:*"
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.ENV.lower() == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.ENV.lower() == "development"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


def reload_settings() -> Settings:
    """Reload settings (clear cache and create new instance)"""
    get_settings.cache_clear()
    return get_settings()