# api/config/settings.py
"""
Application settings with comprehensive configuration management
Environment-based configuration with validation
"""
from typing import Dict, List, Any, Optional
from functools import lru_cache
import torch
from pydantic import BaseSettings, Field, validator
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
    MILVUS_PRIVATE_PORT: int = 19531
    MILVUS_COLLECTION_PREFIX: str = "rag"
    
    # Embedding
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIMENSIONS: int = 1024
    EMBEDDING_BATCH_SIZE: int = 12

    # Device
    DEVICE: str = "cpu"
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    
    # Kafka (for document processing)
    KAFKA_BOOTSTRAP_SERVERS: List[str] = ["localhost:9092"]
    KAFKA_DOCUMENT_TOPIC: str = "document_processing"
    KAFKA_CONSUMER_GROUP: str = "document_processors"
    
    # LLM Providers
    llm_providers: Dict[str, LLMProviderConfig] = Field(default_factory=dict)
    
    # Workflow
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    
    # Orchestrator  
    orchestrator: OrchestratorConfig = Field(default_factory=OrchestratorConfig)
    
    # Milvus
    milvus: MilvusConfig = Field(default_factory=MilvusConfig)
    
    # Storage
    storage: StorageConfig = Field(default_factory=StorageConfig)
    
    # Embedding
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    
    @validator('llm_providers', pre=True, always=True)
    def setup_default_providers(cls, v):
        """Setup default LLM provider configurations"""
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
                    "max_retries": 3,
                    "api_keys": []
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
                    "timeout": 120,
                    "api_keys": []
                }
            ),
            "mistral": LLMProviderConfig(
                name="mistral",
                enabled=False,
                models=["mistral-large-latest", "mistral-small-latest"],
                default_model="mistral-large-latest",
                config={
                    "base_url": "https://api.mistral.ai/v1", 
                    "timeout": 90,
                    "api_keys": []
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
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        """Get device"""
        return device
    
    def get_enabled_providers(self) -> List[str]:
        """Get list of enabled LLM providers"""
        return [name for name, config in self.llm_providers.items() if config.enabled]
    
    def get_enabled_agents(self) -> Dict[str, Any]:
        """Get enabled agents (loaded from database)"""
        return {}
    
    def get_enabled_tools(self) -> Dict[str, Any]:
        """Get enabled tools (loaded from database)"""
        return {}
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        
        fields = {
            'llm_providers': {
                'env': 'LLM_PROVIDERS_JSON'
            }
        }

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()