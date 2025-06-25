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
    provider: str = Field(default="gemini")  # Provider riêng cho từng agent
    confidence_threshold: float = Field(default=0.7)
    temperature: float = Field(default=0.7)  # Temperature setting cho agent
    max_tokens: int = Field(default=8192)    # Max tokens cho agent

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
    
    # Infrastructure Configs
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    vector_db: VectorConfig = Field(default_factory=VectorConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    
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
            enabled=False,  # Default disabled
            config={
                "api_key": os.getenv("MISTRAL_API_KEY", ""),
                "timeout": 60,
                "temperature": 0.7
            },
            models=["mistral-large-latest", "mistral-medium-latest", "mistral-small-latest"],
            default_model="mistral-large-latest"
        ),
        "meta": LLMProviderConfig(
            name="meta",
            enabled=False,  # Default disabled
            config={
                "api_key": os.getenv("META_API_KEY", ""),
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
        )
    })
    
    # Agents - Configurable capabilities với provider riêng
    agents: Dict[str, AgentConfig] = Field(default_factory=lambda: {
        "hr_specialist": AgentConfig(
            name="hr_specialist",
            enabled=True,
            domain="hr",
            capabilities=[
                "policy_analysis", "compensation_queries", "employee_benefits",
                "workplace_regulations", "performance_management"
            ],
            tools=["document_search", "web_search"],
            model="gemini-2.0-flash",
            provider="gemini",  # Specific provider cho HR agent
            confidence_threshold=0.75
        ),
        "finance_specialist": AgentConfig(
            name="finance_specialist",
            enabled=True,
            domain="finance",
            capabilities=[
                "financial_analysis", "budget_planning", "cost_analysis",
                "tax_regulations", "audit_procedures"
            ],
            tools=["document_search", "calculation", "web_search"],
            model="llama3.1:8b",
            provider="ollama",  # Finance agent dùng Ollama
            confidence_threshold=0.75
        ),
        "it_specialist": AgentConfig(
            name="it_specialist",
            enabled=True,
            domain="it",
            capabilities=[
                "infrastructure_analysis", "security_assessment", "software_development",
                "system_troubleshooting", "technology_planning"
            ],
            tools=["document_search", "web_search", "code_generation"],
            model="mistral-large-latest", 
            provider="mistral",  # IT agent dùng Mistral
            confidence_threshold=0.70
        ),
        "general_assistant": AgentConfig(
            name="general_assistant",
            enabled=True,
            domain="general",
            capabilities=[
                "general_research", "information_synthesis", "communication_support",
                "task_coordination", "multi_domain_analysis"
            ],
            tools=["web_search", "document_search", "translation"],
            model="llama-3.1-405b",
            provider="meta",  # General agent dùng Meta
            confidence_threshold=0.60
        )
    })
    
    # Tools - Dynamic configuration
    tools: Dict[str, Dict[str, Any]] = Field(default_factory=lambda: {
        "document_search": {
            "enabled": True,
            "config": {
                "top_k": 5,
                "threshold": 0.7,
                "timeout": 30
            }
        },
        "web_search": {
            "enabled": True,
            "config": {
                "engine": "duckduckgo",
                "max_results": 5,
                "timeout": 10,
                "region": "vn-vi"
            }
        },
        "calculation": {
            "enabled": True,
            "config": {
                "max_expression_length": 1000,
                "timeout": 5
            }
        },
        "datetime": {
            "enabled": True,
            "config": {
                "timezone": "Asia/Ho_Chi_Minh",
                "formats": ["current", "date", "time", "detailed"]
            }
        }
    })
    
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
        "embedding_dimensions": 1024
    })
    
    # Multi-language Support - Remove hardcoded keywords
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
    
    def get_enabled_providers(self) -> List[str]:
        return [name for name, config in self.llm_providers.items() if config.enabled]
    
    def get_enabled_agents(self) -> List[str]:
        return [name for name, config in self.agents.items() if config.enabled]
    
    def get_enabled_tools(self) -> List[str]:
        return [name for name, config in self.tools.items() if config.get("enabled", False)]
    
    def get_agent_config(self, agent_name: str) -> Optional[AgentConfig]:
        return self.agents.get(agent_name)
    
    def get_tool_config(self, tool_name: str) -> Optional[Dict[str, Any]]:
        return self.tools.get(tool_name, {}).get("config")
    
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