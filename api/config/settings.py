from typing import Optional, List, Dict, Any
from pydantic import BaseSettings, validator
from enum import Enum
import os


class Environment(str, Enum):
    DEV = "dev"
    STG = "stg"
    PROD = "prod"


class LLMProvider(str, Enum):
    OLLAMA = "ollama"
    GEMINI = "gemini"
    MISTRAL = "mistral"
    META = "meta"


class Settings(BaseSettings):
    """
    Cấu hình ứng dụng với hỗ trợ multi-environment và multi-LLM providers
    Sử dụng SQLAlchemy cho database operations
    """
    
    APP_NAME: str = "Agentic RAG System"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Environment = Environment.DEV
    DEBUG: bool = False
    
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"
    
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    TIMEZONE: str = "Asia/Ho_Chi_Minh"
    
    DATABASE_HOST: str = "postgres"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "agentic_rag"
    DATABASE_USER: str = "postgres"
    DATABASE_PASSWORD: str
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 3600
    DATABASE_ECHO: bool = False
    DATABASE_ECHO_POOL: bool = False
    DATABASE_POOL_PRE_PING: bool = True
    
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    REDIS_MAX_CONNECTIONS: int = 10
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 5
    REDIS_RETRY_ON_TIMEOUT: bool = True
    
    MILVUS_HOST: str = "milvus-standalone"
    MILVUS_PORT: int = 19530
    MILVUS_USER: Optional[str] = None
    MILVUS_PASSWORD: Optional[str] = None
    MILVUS_DB_NAME: str = "default"
    MILVUS_SECURE: bool = False
    MILVUS_TIMEOUT: int = 30
    
    MINIO_HOST: str = "minio"
    MINIO_PORT: int = 9000
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_SECURE: bool = False
    MINIO_BUCKET_PREFIX: str = "agentic-rag"
    MINIO_REGION: str = "us-east-1"
    
    EMBEDDING_MODEL_PATH: str = "BAAI/bge-M3"
    EMBEDDING_MODEL_DEVICE: str = "cpu"
    EMBEDDING_BATCH_SIZE: int = 32
    EMBEDDING_MAX_LENGTH: int = 8192
    EMBEDDING_DIMENSION: int = 1024
    EMBEDDING_CACHE_SIZE: int = 10000
    
    DEFAULT_LLM_PROVIDER: LLMProvider = LLMProvider.OLLAMA
    
    OLLAMA_HOST: str = "ollama"
    OLLAMA_PORT: int = 11434
    OLLAMA_DEFAULT_MODEL: str = "llama3.1:8b"
    OLLAMA_TIMEOUT: int = 120
    
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_DEFAULT_MODEL: str = "gemini-1.5-pro"
    GEMINI_TIMEOUT: int = 60
    
    MISTRAL_API_KEY: Optional[str] = None
    MISTRAL_DEFAULT_MODEL: str = "mistral-large-latest"
    MISTRAL_TIMEOUT: int = 60
    
    META_API_KEY: Optional[str] = None
    META_DEFAULT_MODEL: str = "llama-3.1-405b"
    META_TIMEOUT: int = 60
    
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    RATE_LIMIT_PER_DAY: int = 10000
    
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_ROTATION_SIZE: str = "10MB"
    LOG_RETENTION_COUNT: int = 5
    LOG_FILE_PATH: str = "/app/logs"
    
    CORS_ORIGINS: List[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    WEBHOOK_SECRET: Optional[str] = None
    WEBHOOK_TIMEOUT: int = 30
    WEBHOOK_RETRY_ATTEMPTS: int = 3
    
    DOCUMENT_MAX_SIZE_MB: int = 50
    DOCUMENT_ALLOWED_EXTENSIONS: List[str] = [
        ".pdf", ".docx", ".doc", ".txt", ".md", ".html", 
        ".xlsx", ".xls", ".pptx", ".ppt", ".csv", ".json"
    ]
    DOCUMENT_PROCESSING_TIMEOUT: int = 300
    
    CACHE_TTL_SECONDS: int = 300
    CACHE_MAX_SIZE: int = 1000
    CACHE_CLEANUP_INTERVAL: int = 3600
    
    HEALTH_CHECK_INTERVAL: int = 60
    PERFORMANCE_MONITORING: bool = True
    METRICS_COLLECTION: bool = True
    
    MULTI_TENANT_ENABLED: bool = True
    DEFAULT_TENANT_ID: str = "default"
    TENANT_ISOLATION_LEVEL: str = "strict"
    
    SECURITY_PASSWORD_MIN_LENGTH: int = 8
    SECURITY_PASSWORD_REQUIRE_UPPER: bool = True
    SECURITY_PASSWORD_REQUIRE_LOWER: bool = True
    SECURITY_PASSWORD_REQUIRE_DIGIT: bool = True
    SECURITY_PASSWORD_REQUIRE_SPECIAL: bool = True
    SECURITY_MAX_LOGIN_ATTEMPTS: int = 5
    SECURITY_LOCKOUT_DURATION: int = 900
    
    WORKFLOW_MAX_EXECUTION_TIME: int = 600
    WORKFLOW_MAX_RETRIES: int = 3
    WORKFLOW_CHECKPOINT_INTERVAL: int = 30
    
    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        if v not in [Environment.DEV, Environment.STG, Environment.PROD]:
            raise ValueError("ENVIRONMENT phải là dev, stg hoặc prod")
        return v
    
    @validator("DATABASE_PASSWORD")
    def validate_database_password(cls, v):
        if not v:
            raise ValueError("DATABASE_PASSWORD là bắt buộc")
        return v
    
    @validator("SECRET_KEY")
    def validate_secret_key(cls, v):
        if not v or len(v) < 32:
            raise ValueError("SECRET_KEY phải có ít nhất 32 ký tự")
        return v
    
    @validator("MINIO_ACCESS_KEY", "MINIO_SECRET_KEY")
    def validate_minio_credentials(cls, v):
        if not v:
            raise ValueError("MinIO credentials là bắt buộc")
        return v
    
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == Environment.DEV
    
    @property
    def is_staging(self) -> bool:
        return self.ENVIRONMENT == Environment.STG
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == Environment.PROD
    
    @property
    def database_url(self) -> str:
        """SQLAlchemy database URL cho sync operations"""
        return f"postgresql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
    
    @property
    def async_database_url(self) -> str:
        """SQLAlchemy async database URL cho async operations"""
        return f"postgresql+asyncpg://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
    
    @property
    def redis_url(self) -> str:
        """Redis connection URL"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def minio_endpoint(self) -> str:
        """MinIO endpoint URL"""
        return f"{self.MINIO_HOST}:{self.MINIO_PORT}"
    
    @property
    def ollama_base_url(self) -> str:
        """Ollama base URL"""
        return f"http://{self.OLLAMA_HOST}:{self.OLLAMA_PORT}"
    
    def get_sqlalchemy_config(self) -> Dict[str, Any]:
        """Lấy cấu hình SQLAlchemy"""
        config = {
            "pool_size": self.DATABASE_POOL_SIZE,
            "max_overflow": self.DATABASE_MAX_OVERFLOW,
            "pool_timeout": self.DATABASE_POOL_TIMEOUT,
            "pool_recycle": self.DATABASE_POOL_RECYCLE,
            "pool_pre_ping": self.DATABASE_POOL_PRE_PING,
            "echo": self.DATABASE_ECHO,
            "echo_pool": self.DATABASE_ECHO_POOL,
        }
        
        if self.is_development:
            config.update({
                "echo": True,
                "echo_pool": True,
            })
        elif self.is_production:
            config.update({
                "pool_size": self.DATABASE_POOL_SIZE * 2,
                "max_overflow": self.DATABASE_MAX_OVERFLOW * 2,
                "echo": False,
                "echo_pool": False,
            })
        
        return config
    
    def get_redis_config(self) -> Dict[str, Any]:
        """Lấy cấu hình Redis"""
        return {
            "host": self.REDIS_HOST,
            "port": self.REDIS_PORT,
            "password": self.REDIS_PASSWORD,
            "db": self.REDIS_DB,
            "max_connections": self.REDIS_MAX_CONNECTIONS,
            "socket_timeout": self.REDIS_SOCKET_TIMEOUT,
            "socket_connect_timeout": self.REDIS_SOCKET_CONNECT_TIMEOUT,
            "retry_on_timeout": self.REDIS_RETRY_ON_TIMEOUT,
            "decode_responses": True,
            "encoding": "utf-8"
        }
    
    def get_milvus_config(self) -> Dict[str, Any]:
        """Lấy cấu hình Milvus"""
        config = {
            "host": self.MILVUS_HOST,
            "port": self.MILVUS_PORT,
            "db_name": self.MILVUS_DB_NAME,
            "secure": self.MILVUS_SECURE,
            "timeout": self.MILVUS_TIMEOUT
        }
        
        if self.MILVUS_USER and self.MILVUS_PASSWORD:
            config.update({
                "user": self.MILVUS_USER,
                "password": self.MILVUS_PASSWORD
            })
        
        return config
    
    def get_llm_config(self, provider: Optional[LLMProvider] = None) -> Dict[str, Any]:
        """Lấy cấu hình LLM provider"""
        provider = provider or self.DEFAULT_LLM_PROVIDER
        
        configs = {
            LLMProvider.OLLAMA: {
                "provider": "ollama",
                "base_url": self.ollama_base_url,
                "model": self.OLLAMA_DEFAULT_MODEL,
                "timeout": self.OLLAMA_TIMEOUT,
                "api_key": None
            },
            LLMProvider.GEMINI: {
                "provider": "gemini",
                "base_url": "https://generativelanguage.googleapis.com/v1beta",
                "model": self.GEMINI_DEFAULT_MODEL,
                "timeout": self.GEMINI_TIMEOUT,
                "api_key": self.GEMINI_API_KEY
            },
            LLMProvider.MISTRAL: {
                "provider": "mistral",
                "base_url": "https://api.mistral.ai/v1",
                "model": self.MISTRAL_DEFAULT_MODEL,
                "timeout": self.MISTRAL_TIMEOUT,
                "api_key": self.MISTRAL_API_KEY
            },
            LLMProvider.META: {
                "provider": "meta",
                "base_url": "https://api.llama-api.com",
                "model": self.META_DEFAULT_MODEL,
                "timeout": self.META_TIMEOUT,
                "api_key": self.META_API_KEY
            }
        }
        
        if provider not in configs:
            raise ValueError(f"Provider {provider} không được hỗ trợ")
        
        return configs[provider]
    
    def get_environment_config(self) -> Dict[str, Any]:
        """Lấy cấu hình theo environment"""
        base_config = {
            "log_level": self.LOG_LEVEL,
            "debug": self.DEBUG,
            "cache_ttl": self.CACHE_TTL_SECONDS,
            "performance_monitoring": self.PERFORMANCE_MONITORING,
            "metrics_collection": self.METRICS_COLLECTION,
            "rate_limits": {
                "per_minute": self.RATE_LIMIT_PER_MINUTE,
                "per_hour": self.RATE_LIMIT_PER_HOUR,
                "per_day": self.RATE_LIMIT_PER_DAY
            }
        }
        
        environment_configs = {
            Environment.DEV: {
                "log_level": "DEBUG",
                "debug": True,
                "cache_ttl": 60,
                "rate_limits": {
                    "per_minute": 120,
                    "per_hour": 2000,
                    "per_day": 20000
                }
            },
            Environment.STG: {
                "log_level": "INFO",
                "debug": False,
                "cache_ttl": 300,
                "rate_limits": {
                    "per_minute": 100,
                    "per_hour": 1500,
                    "per_day": 15000
                }
            },
            Environment.PROD: {
                "log_level": "WARNING",
                "debug": False,
                "cache_ttl": 600,
                "rate_limits": {
                    "per_minute": 80,
                    "per_hour": 1000,
                    "per_day": 10000
                }
            }
        }
        
        env_config = environment_configs.get(self.ENVIRONMENT, {})
        base_config.update(env_config)
        
        return base_config
    
    def get_security_config(self) -> Dict[str, Any]:
        """Lấy cấu hình bảo mật"""
        return {
            "password_policy": {
                "min_length": self.SECURITY_PASSWORD_MIN_LENGTH,
                "require_upper": self.SECURITY_PASSWORD_REQUIRE_UPPER,
                "require_lower": self.SECURITY_PASSWORD_REQUIRE_LOWER,
                "require_digit": self.SECURITY_PASSWORD_REQUIRE_DIGIT,
                "require_special": self.SECURITY_PASSWORD_REQUIRE_SPECIAL
            },
            "login_security": {
                "max_attempts": self.SECURITY_MAX_LOGIN_ATTEMPTS,
                "lockout_duration": self.SECURITY_LOCKOUT_DURATION
            },
            "token_security": {
                "access_token_expire": self.ACCESS_TOKEN_EXPIRE_MINUTES,
                "refresh_token_expire": self.REFRESH_TOKEN_EXPIRE_DAYS
            }
        }
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        use_enum_values = True


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Singleton pattern để lấy settings instance
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """
    Reload settings từ environment variables
    """
    global _settings
    _settings = Settings()
    return _settings