from typing import Dict, Any, Optional, List, Union
import os
from functools import lru_cache
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    """
    Extended Application configuration với LangGraph integration.
    Supports multi-provider LLM, tool management, và admin controls.
    """
    
    # Basic App Configuration
    ENV: str = Field(default="dev")
    DEBUG: bool = Field(default=True)
    
    APP_NAME: str = Field(default="Agentic RAG API")
    APP_HOST: str = Field(default="0.0.0.0")
    APP_PORT: int = Field(default=8000)
    BOT_NAME: str = Field(default="NewwaveBot")
    TIMEZONE: str = Field(default="Asia/Ho_Chi_Minh")
    
    # Production worker configuration
    WORKERS: int = Field(default=4)
    WORKER_CLASS: str = Field(default="uvicorn.workers.UvicornWorker")
    WORKER_CONNECTIONS: int = Field(default=1000)
    MAX_REQUESTS: int = Field(default=1000)
    MAX_REQUESTS_JITTER: int = Field(default=100)
    KEEPALIVE: int = Field(default=2)
    
    # Security settings
    SECRET_KEY: str = Field(default="secret_key_development_only")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    ALLOWED_HOSTS: List[str] = Field(default=["*"])
    CORS_ORIGINS: List[str] = Field(default=["*"])
    ENABLE_DOCS: bool = Field(default=True)
    
    # Database configurations
    DATABASE_URL: str = Field(default="postgresql://postgres:postgres@db-postgres:5432/newwave_chatbot")
    
    # Milvus Vector Database
    MILVUS_HOST: str = Field(default="db-milvus")
    MILVUS_PORT: Union[str, int] = Field(default="19530")
    MILVUS_USER: str = Field(default="milvus")
    MILVUS_PASSWORD: str = Field(default="milvus")
    MILVUS_COLLECTION: str = Field(default="chatbot")
    
    # Redis Configuration (for caching and state management)
    REDIS_HOST: str = Field(default="redis")
    REDIS_PORT: int = Field(default=6379)
    REDIS_PASSWORD: Optional[str] = Field(default=None)
    REDIS_DB: int = Field(default=0)
    CACHE_TTL: int = Field(default=3600)  # 1 hour
    
    # MinIO Object Storage
    MINIO_ENDPOINT: str = Field(default="minio:9000")
    MINIO_EXTERNAL_ENDPOINT: str = Field(default="localhost:9000")  
    MINIO_ACCESS_KEY: str = Field(default="minioadmin")
    MINIO_SECRET_KEY: str = Field(default="minioadmin")
    MINIO_SECURE: bool = Field(default=False)
    MINIO_EXTERNAL_SECURE: bool = Field(default=False)
    MINIO_BUCKET_NAME: str = Field(default="newwave-documents")
    MINIO_REGION: Optional[str] = Field(default=None)
    
    # File Upload Settings
    UPLOAD_DIR: str = Field(default="/app/uploads")
    VERSIONS_DIR: str = Field(default="/app/versions")
    MAX_FILE_SIZE: int = Field(default=100 * 1024 * 1024)
    ALLOWED_FILE_TYPES: List[str] = Field(default=[
        "application/pdf", 
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
        "text/plain",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-powerpoint"
    ])
    
    # ================================
    # MULTI-PROVIDER LLM CONFIGURATION
    # ================================
    
    # Default Provider Settings (Admin configurable)
    DEFAULT_LLM_PROVIDER: str = Field(default="gemini")
    FALLBACK_LLM_PROVIDER: str = Field(default="gemini")
    FUNCTION_CALLING_PROVIDER: str = Field(default="gemini")
    
    # Provider Enable/Disable Controls (Admin managed)
    ENABLE_GEMINI_PROVIDER: bool = Field(default=True)
    ENABLE_OLLAMA_PROVIDER: bool = Field(default=True)
    ENABLE_MISTRAL_PROVIDER: bool = Field(default=False)
    ENABLE_META_PROVIDER: bool = Field(default=False)
    ENABLE_ANTHROPIC_PROVIDER: bool = Field(default=False)
    
    # Gemini Configuration
    GEMINI_API_KEY: str = Field(default="AIzaSyCm-NmIFZZusArL44jibAPi3VOAUuEEjxk,AIzaSyBZ3smYn1uK94IJ32GKblcK3dThdJddY5U,AIzaSyBZ8_6FCP42G5quv7M-TdS3--ezjDvu2H0,AIzaSyBZMvDpFfJ1lHZp8yN0-ZKSN55egI2mcT0,AIzaSyD5pSaoA88TV58XM0_acLd-R1zIb7zy6mE")
    GEMINI_DEFAULT_MODEL: str = Field(default="gemini-2.0-flash")
    GEMINI_DEFAULT_MAX_TOKENS: int = Field(default=8192)
    GEMINI_TIMEOUT: int = Field(default=60)
    
    # Ollama Configuration
    OLLAMA_API_URL: str = Field(default="http://192.168.200.57:11434")
    OLLAMA_DEFAULT_MODEL: str = Field(default="llama3.1:8b")
    OLLAMA_KEEP_ALIVE: int = Field(default=-1)
    OLLAMA_MAX_LOADED_MODELS: int = Field(default=2)
    OLLAMA_NUM_PARALLEL: int = Field(default=2)
    OLLAMA_FLASH_ATTENTION: bool = Field(default=True)
    OLLAMA_TIMEOUT: int = Field(default=120)
    
    # Mistral Configuration
    MISTRAL_API_KEY: Optional[str] = Field(default=None)
    MISTRAL_DEFAULT_MODEL: str = Field(default="mistral-large-latest")
    MISTRAL_TIMEOUT: int = Field(default=60)
    
    # Meta Configuration
    META_API_KEY: Optional[str] = Field(default=None)
    META_DEFAULT_MODEL: str = Field(default="llama-3.1-405b")
    META_TIMEOUT: int = Field(default=60)
    
    # Anthropic Configuration
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None)
    ANTHROPIC_DEFAULT_MODEL: str = Field(default="claude-3-5-sonnet-20241022")
    ANTHROPIC_TIMEOUT: int = Field(default=60)
    
    # ================================
    # TOOL MANAGEMENT CONFIGURATION
    # ================================
    
    # Tool Enable/Disable Controls (Admin managed)
    ENABLE_WEB_SEARCH_TOOL: bool = Field(default=True)
    ENABLE_DOCUMENT_SEARCH_TOOL: bool = Field(default=True)
    ENABLE_CALCULATION_TOOL: bool = Field(default=True)
    ENABLE_DATE_TIME_TOOL: bool = Field(default=True)
    ENABLE_FILE_ANALYSIS_TOOL: bool = Field(default=True)
    ENABLE_SUMMARIZATION_TOOL: bool = Field(default=True)
    ENABLE_TRANSLATION_TOOL: bool = Field(default=True)
    ENABLE_CODE_GENERATION_TOOL: bool = Field(default=False)
    ENABLE_IMAGE_ANALYSIS_TOOL: bool = Field(default=False)
    ENABLE_EMAIL_TOOL: bool = Field(default=False)
    
    # Web Search Tool Configuration
    WEB_SEARCH_ENGINE: str = Field(default="duckduckgo")  # duckduckgo, google, bing
    WEB_SEARCH_MAX_RESULTS: int = Field(default=5)
    WEB_SEARCH_TIMEOUT: int = Field(default=10)
    
    # ================================
    # EMBEDDING MODEL CONFIGURATION
    # ================================
    
    EMBEDDING_MODEL: str = Field(default="BAAI/bge-m3")
    EMBEDDING_MODEL_DEVICE: str = Field(default="cpu")
    EMBEDDING_MODEL_MAX_LENGTH: int = Field(default=512)
    EMBEDDING_DIMENSIONS: int = Field(default=1024)  # BGE-M3 dimensions
    EMBEDDING_BATCH_SIZE: int = Field(default=32)
    
    # Document Processing
    DEFAULT_CHUNK_SIZE: int = Field(default=512)
    DEFAULT_CHUNK_OVERLAP: int = Field(default=128)
    
    # ================================
    # RAG CONFIGURATION
    # ================================
    
    DEFAULT_TOP_K: int = Field(default=5)
    DEFAULT_THRESHOLD: float = Field(default=0.2)
    DEFAULT_MAX_TOKENS: int = Field(default=8192)
    DEFAULT_RAG_MAX_TOKENS: int = Field(default=8192)
    NUM_FOLLOW_UP_QUESTIONS: int = Field(default=3)
    CHAT_SESSION_TITLE_MAX_WORDS: int = Field(default=10)
    CHAT_SESSION_TITLE_MAX_CHARS: int = Field(default=100)
    
    # ================================
    # LANGGRAPH CONFIGURATION
    # ================================
    
    LANGGRAPH_MEMORY_SIZE: int = Field(default=100)  # Max memory items
    LANGGRAPH_MAX_ITERATIONS: int = Field(default=10)  # Max workflow iterations
    LANGGRAPH_TIMEOUT: int = Field(default=300)  # 5 minutes timeout
    ENABLE_LANGGRAPH_DEBUG: bool = Field(default=False)
    LANGGRAPH_CHECKPOINTER_TYPE: str = Field(default="redis")  # redis, postgres, memory
    
    # Agent Configuration (Admin configurable models per agent)
    ROUTER_MODEL: str = Field(default="gemini-2.0-flash")
    RETRIEVAL_MODEL: str = Field(default="gemini-2.0-flash")
    SYNTHESIS_MODEL: str = Field(default="gemini-2.0-flash")
    REFLECTION_MODEL: str = Field(default="gemini-2.0-flash")
    SEMANTIC_ROUTER_MODEL: str = Field(default="gemini-2.0-flash")
    RESPONSE_GENERATION_MODEL: str = Field(default="gemini-2.0-flash")
    FUNCTION_CALLING_MODEL: str = Field(default="gemini-2.0-flash")
    DEFAULT_CHAT_MODEL: str = Field(default="gemini-2.0-flash")
    
    # ================================
    # INTELLIGENT ORCHESTRATOR CONFIGURATION
    # ================================
    
    # Orchestrator LLM (Admin configurable - thay thế hardcode keywords)
    ORCHESTRATOR_MODEL: str = Field(default="gemini-2.0-flash")
    ENABLE_INTELLIGENT_ORCHESTRATOR: bool = Field(default=True)
    ORCHESTRATOR_CONFIDENCE_THRESHOLD: float = Field(default=0.7)
    ORCHESTRATOR_TIMEOUT: int = Field(default=30)  # seconds
    
    # Agent selection strategy (Admin configurable)
    AGENT_SELECTION_STRATEGY: str = Field(default="llm_orchestrator")  # llm_orchestrator, keyword_matching, hybrid
    ENABLE_CROSS_DOMAIN_ANALYSIS: bool = Field(default=True)
    MAX_AGENTS_PER_QUERY: int = Field(default=3)
    
    # Agent capabilities (Admin configurable thay vì hardcode)
    ENABLE_DOMAIN_EXPERTISE_ANALYSIS: bool = Field(default=True)
    ENABLE_COMPLEXITY_SCORING: bool = Field(default=True)
    ENABLE_EXECUTION_TIME_ESTIMATION: bool = Field(default=True)
    
    # ================================
    # WORKFLOW CONFIGURATION
    # ================================
    
    # Workflow Enable/Disable (Admin managed)
    ENABLE_REFLECTION_WORKFLOW: bool = Field(default=True)
    ENABLE_SEMANTIC_ROUTING: bool = Field(default=True)
    ENABLE_DOCUMENT_GRADING: bool = Field(default=True)
    ENABLE_CITATION_GENERATION: bool = Field(default=True)
    ENABLE_QUERY_EXPANSION: bool = Field(default=True)
    ENABLE_ANSWER_HALLUCINATION_CHECK: bool = Field(default=True)
    
    # ================================
    # DEPRECATED: KEYWORD-BASED SELECTION (Kept for fallback only)
    # ================================
    
    # Note: Replaced by Intelligent Orchestrator LLM
    # These are kept for backward compatibility and fallback scenarios
    
    # Default language for keywords (Admin configurable) 
    DEFAULT_KEYWORDS_LANGUAGE: str = Field(default="vi")
    
    # Agent specialist keywords (DEPRECATED - Admin configurable, multi-language support)
    # Now only used as fallback when LLM orchestrator fails
    HR_KEYWORDS: Dict[str, List[str]] = Field(default={
        "vi": ["nhân sự", "chính sách", "quy định", "lương", "thưởng", "phúc lợi", "bảo hiểm", "làm việc từ xa", "đào tạo", "phát triển", "đánh giá", "nghỉ phép"],
        "en": ["hr", "human resource", "policy", "salary", "compensation", "bonus", "benefit", "insurance", "remote", "work from home", "training", "development", "performance", "kpi", "leave", "vacation"],
        "ja": ["人事", "ポリシー", "給与", "報酬", "福利厚生", "保険", "リモートワーク", "在宅勤務", "研修", "開発", "評価", "休暇"],
        "ko": ["인사", "정책", "급여", "보상", "복리후생", "보험", "원격근무", "재택근무", "교육", "개발", "평가", "휴가"]
    })
    
    FINANCE_KEYWORDS: Dict[str, List[str]] = Field(default={
        "vi": ["tài chính", "kế toán", "ngân sách", "chi phí", "doanh thu", "lợi nhuận", "đầu tư", "thuế", "báo cáo tài chính", "kiểm toán"],
        "en": ["finance", "accounting", "budget", "cost", "revenue", "profit", "investment", "tax", "financial report", "audit"],
        "ja": ["財務", "会計", "予算", "コスト", "収益", "利益", "投資", "税金", "財務報告", "監査"],
        "ko": ["재무", "회계", "예산", "비용", "수익", "이익", "투자", "세금", "재무보고", "감사"]
    })
    
    IT_KEYWORDS: Dict[str, List[str]] = Field(default={
        "vi": ["công nghệ", "hệ thống", "phần mềm", "phần cứng", "mạng", "bảo mật", "dữ liệu", "server", "database", "api"],
        "en": ["technology", "system", "software", "hardware", "network", "security", "data", "server", "database", "api"],
        "ja": ["技術", "システム", "ソフトウェア", "ハードウェア", "ネットワーク", "セキュリティ", "データ", "サーバー", "データベース"],
        "ko": ["기술", "시스템", "소프트웨어", "하드웨어", "네트워크", "보안", "데이터", "서버", "데이터베이스"]
    })
    
    # Tool indicators (DEPRECATED - Admin configurable, multi-language support)
    # Now handled by LLM orchestrator semantic analysis
    WEB_SEARCH_INDICATORS: Dict[str, List[str]] = Field(default={
        "vi": ["tin tức", "thời sự", "mới nhất", "hiện tại", "giá", "thị trường", "cổ phiếu", "thời tiết", "dự báo", "kết quả", "bảng xếp hạng", "tìm kiếm"],
        "en": ["news", "current", "latest", "now", "price", "market", "stock", "weather", "forecast", "result", "ranking", "search", "google"],
        "ja": ["ニュース", "最新", "現在", "価格", "市場", "株式", "天気", "予報", "結果", "ランキング", "検索"],
        "ko": ["뉴스", "최신", "현재", "가격", "시장", "주식", "날씨", "예보", "결과", "순위", "검색"]
    })
    
    DOCUMENT_SEARCH_INDICATORS: Dict[str, List[str]] = Field(default={
        "vi": ["tài liệu", "file", "pdf", "báo cáo", "quy định", "hướng dẫn", "sổ tay", "chính sách"],
        "en": ["document", "file", "pdf", "report", "policy", "instruction", "manual", "handbook", "guideline"],
        "ja": ["文書", "ファイル", "レポート", "ポリシー", "指示", "マニュアル", "ハンドブック"],
        "ko": ["문서", "파일", "보고서", "정책", "지침", "매뉴얼", "핸드북"]
    })
    
    CALCULATION_INDICATORS: Dict[str, List[str]] = Field(default={
        "vi": ["tính", "toán", "phép", "chia", "nhân", "cộng", "trừ", "kết quả", "bằng"],
        "en": ["calculate", "math", "compute", "plus", "minus", "multiply", "divide", "equals", "result"],
        "ja": ["計算", "数学", "足し算", "引き算", "掛け算", "割り算", "結果", "等しい"],
        "ko": ["계산", "수학", "더하기", "빼기", "곱하기", "나누기", "결과", "같다"]
    })
    
    DATETIME_INDICATORS: Dict[str, List[str]] = Field(default={
        "vi": ["thời gian", "ngày", "tháng", "năm", "giờ", "phút", "hôm nay", "ngày mai", "hôm qua", "tuần", "thứ"],
        "en": ["time", "date", "day", "month", "year", "hour", "minute", "today", "tomorrow", "yesterday", "week", "monday", "tuesday"],
        "ja": ["時間", "日付", "日", "月", "年", "時", "分", "今日", "明日", "昨日", "週", "月曜日"],
        "ko": ["시간", "날짜", "일", "월", "년", "시", "분", "오늘", "내일", "어제", "주", "월요일"]
    })
    
    # Weekday names (Admin configurable, multi-language support)
    WEEKDAY_NAMES: Dict[str, Dict[int, str]] = Field(default={
        "vi": {0: "Thứ Hai", 1: "Thứ Ba", 2: "Thứ Tư", 3: "Thứ Năm", 4: "Thứ Sáu", 5: "Thứ Bảy", 6: "Chủ Nhật"},
        "en": {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"},
        "ja": {0: "月曜日", 1: "火曜日", 2: "水曜日", 3: "木曜日", 4: "金曜日", 5: "土曜日", 6: "日曜日"},
        "ko": {0: "월요일", 1: "화요일", 2: "수요일", 3: "목요일", 4: "금요일", 5: "토요일", 6: "일요일"}
    })
    
    # Unknown/fallback text (Admin configurable, multi-language support)
    UNKNOWN_WEEKDAY_TEXT: Dict[str, str] = Field(default={
        "vi": "Không xác định",
        "en": "Unknown", 
        "ja": "不明",
        "ko": "알 수 없음"
    })
    
    # Web search configuration (Admin configurable)
    WEB_SEARCH_REGION: str = Field(default="vn-vi")
    WEB_SEARCH_SAFESEARCH: str = Field(default="moderate")
    
    # Agent configuration (Admin configurable)
    ENABLED_AGENTS: Dict[str, bool] = Field(default={
        "hr_specialist": True,
        "finance_specialist": True, 
        "it_specialist": True,
        "general_assistant": True,
        "coordinator": True,
        "conflict_resolver": True,
        "synthesizer": True
    })
    
    # Performance Settings
    MAX_CONCURRENT_REQUESTS: int = Field(default=100)
    REQUEST_TIMEOUT: int = Field(default=60)
    
    # ================================
    # MULTI-TENANT SUPPORT
    # ================================
    
    ENABLE_MULTI_TENANT: bool = Field(default=False)
    DEFAULT_TENANT_ID: str = Field(default="default")
    
    # ================================
    # AUTHENTICATION & AUTHORIZATION
    # ================================
    
    # GitLab OAuth (Optional)
    GITLAB_CLIENT_ID: str = Field(default="")
    GITLAB_CLIENT_SECRET: str = Field(default="")
    GITLAB_REDIRECT_URI: str = Field(default="http://localhost:8000/auth/gitlab/callback")
    GITLAB_BASE_URL: str = Field(default="https://gitlab.com")
    
    # OTP Configuration
    OTP_SECRET_KEY: str = Field(default="JBSWY3DPEHPK3PXP")
    OTP_VALIDITY_SECONDS: int = Field(default=30)
    OTP_TOLERANCE_WINDOWS: int = Field(default=2)
    
    # ================================
    # ADMIN INTERFACE CONFIGURATION
    # ================================
    
    ENABLE_ADMIN_INTERFACE: bool = Field(default=True)
    ADMIN_SECRET_KEY: str = Field(default="admin_secret_development_only")
    
    # ================================
    # PROPERTIES & COMPUTED VALUES
    # ================================
    
    @property
    def gemini_api_keys(self) -> List[str]:
        """Get list of Gemini API keys from comma-separated string"""
        if not self.GEMINI_API_KEY:
            return []
        return [key.strip() for key in self.GEMINI_API_KEY.split(",") if key.strip()]
    
    @property
    def redis_url(self) -> str:
        """Build Redis URL from components"""
        auth_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def enabled_providers(self) -> List[str]:
        """Get list of enabled LLM providers"""
        providers = []
        if self.ENABLE_GEMINI_PROVIDER:
            providers.append("gemini")
        if self.ENABLE_OLLAMA_PROVIDER:
            providers.append("ollama")
        if self.ENABLE_MISTRAL_PROVIDER:
            providers.append("mistral")
        if self.ENABLE_META_PROVIDER:
            providers.append("meta")
        if self.ENABLE_ANTHROPIC_PROVIDER:
            providers.append("anthropic")
        return providers
    
    @property
    def enabled_tools(self) -> Dict[str, bool]:
        """Get mapping of tool names to enabled status"""
        return {
            "web_search": self.ENABLE_WEB_SEARCH_TOOL,
            "document_search": self.ENABLE_DOCUMENT_SEARCH_TOOL,
            "calculation": self.ENABLE_CALCULATION_TOOL,
            "date_time": self.ENABLE_DATE_TIME_TOOL,
            "file_analysis": self.ENABLE_FILE_ANALYSIS_TOOL,
            "summarization": self.ENABLE_SUMMARIZATION_TOOL,
            "translation": self.ENABLE_TRANSLATION_TOOL,
            "code_generation": self.ENABLE_CODE_GENERATION_TOOL,
            "image_analysis": self.ENABLE_IMAGE_ANALYSIS_TOOL,
            "email": self.ENABLE_EMAIL_TOOL,
        }
    
    @property
    def enabled_workflows(self) -> Dict[str, bool]:
        """Get mapping of workflow names to enabled status"""
        return {
            "reflection": self.ENABLE_REFLECTION_WORKFLOW,
            "semantic_routing": self.ENABLE_SEMANTIC_ROUTING,
            "document_grading": self.ENABLE_DOCUMENT_GRADING,
            "citation_generation": self.ENABLE_CITATION_GENERATION,
            "query_expansion": self.ENABLE_QUERY_EXPANSION,
            "hallucination_check": self.ENABLE_ANSWER_HALLUCINATION_CHECK,
        }
    
    @property 
    def MAX_FILE_SIZE_MB(self) -> int:
        """Get max file size in MB"""
        return self.MAX_FILE_SIZE // (1024 * 1024)
    
    # ================================
    # VALIDATION METHODS
    # ================================
    
    @field_validator("ENV")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed_envs = ["dev", "stg", "prod"]
        if v not in allowed_envs:
            raise ValueError(f"ENV must be one of {allowed_envs}")
        return v
    
    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith(("postgresql://", "postgres://")):
            raise ValueError("DATABASE_URL must be a valid PostgreSQL connection string")
        return v
    
    @field_validator("MAX_FILE_SIZE")
    @classmethod
    def validate_max_file_size(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("MAX_FILE_SIZE must be positive")
        if v > 1024 * 1024 * 1024:
            raise ValueError("MAX_FILE_SIZE cannot exceed 1GB")
        return v
    
    @field_validator("DEFAULT_TOP_K")
    @classmethod
    def validate_top_k(cls, v: int) -> int:
        if v <= 0 or v > 100:
            raise ValueError("DEFAULT_TOP_K must be between 1 and 100")
        return v
    
    @field_validator("DEFAULT_THRESHOLD")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if v < 0 or v > 1:
            raise ValueError("DEFAULT_THRESHOLD must be between 0 and 1")
        return v
    
    # ================================
    # HELPER METHODS
    # ================================
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.ENV == "prod"
    
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.ENV == "dev"
    
    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """Get configuration for specific LLM provider"""
        provider_configs = {
            "gemini": {
                "provider": "gemini",
                "enabled": self.ENABLE_GEMINI_PROVIDER,
                "api_keys": self.gemini_api_keys,
                "default_model": self.GEMINI_DEFAULT_MODEL,
                "max_tokens": self.GEMINI_DEFAULT_MAX_TOKENS,
                "timeout": self.GEMINI_TIMEOUT,
            },
            "ollama": {
                "provider": "ollama",
                "enabled": self.ENABLE_OLLAMA_PROVIDER,
                "base_url": self.OLLAMA_API_URL,
                "default_model": self.OLLAMA_DEFAULT_MODEL,
                "keep_alive": self.OLLAMA_KEEP_ALIVE,
                "timeout": self.OLLAMA_TIMEOUT,
            },
            "mistral": {
                "provider": "mistral",
                "enabled": self.ENABLE_MISTRAL_PROVIDER,
                "api_key": self.MISTRAL_API_KEY,
                "default_model": self.MISTRAL_DEFAULT_MODEL,
                "timeout": self.MISTRAL_TIMEOUT,
            },
            "meta": {
                "provider": "meta",
                "enabled": self.ENABLE_META_PROVIDER,
                "api_key": self.META_API_KEY,
                "default_model": self.META_DEFAULT_MODEL,
                "timeout": self.META_TIMEOUT,
            },
            "anthropic": {
                "provider": "anthropic",
                "enabled": self.ENABLE_ANTHROPIC_PROVIDER,
                "api_key": self.ANTHROPIC_API_KEY,
                "default_model": self.ANTHROPIC_DEFAULT_MODEL,
                "timeout": self.ANTHROPIC_TIMEOUT,
            }
        }
        
        return provider_configs.get(provider, {})
    
    def get_minio_config(self) -> Dict[str, Any]:
        """Get MinIO configuration dict"""
        return {
            "endpoint": self.MINIO_ENDPOINT,
            "access_key": self.MINIO_ACCESS_KEY,
            "secret_key": self.MINIO_SECRET_KEY,
            "secure": self.MINIO_SECURE,
            "region": self.MINIO_REGION,
            "bucket_name": self.MINIO_BUCKET_NAME
        }
    
    def get_langgraph_config(self) -> Dict[str, Any]:
        """Get LangGraph configuration dict"""
        return {
            "memory_size": self.LANGGRAPH_MEMORY_SIZE,
            "max_iterations": self.LANGGRAPH_MAX_ITERATIONS,
            "timeout": self.LANGGRAPH_TIMEOUT,
            "debug": self.ENABLE_LANGGRAPH_DEBUG,
            "checkpointer_type": self.LANGGRAPH_CHECKPOINTER_TYPE,
            "enabled_workflows": self.enabled_workflows
        }
    
    def get_agent_configs(self) -> Dict[str, str]:
        """Get model assignments for each agent"""
        return {
            "router": self.ROUTER_MODEL,
            "retrieval": self.RETRIEVAL_MODEL,
            "synthesis": self.SYNTHESIS_MODEL,
            "reflection": self.REFLECTION_MODEL,
            "semantic_router": self.SEMANTIC_ROUTER_MODEL,
            "response_generation": self.RESPONSE_GENERATION_MODEL,
            "function_calling": self.FUNCTION_CALLING_MODEL,
            "chat": self.DEFAULT_CHAT_MODEL
        }
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

def get_environment_info() -> Dict[str, Any]:
    """Get environment information for debugging"""
    settings = get_settings()
    return {
        "environment": settings.ENV,
        "debug": settings.DEBUG,
        "app_name": settings.APP_NAME,
        "database_configured": bool(settings.DATABASE_URL),
        "milvus_configured": bool(settings.MILVUS_HOST),
        "redis_configured": bool(settings.REDIS_HOST),
        "gemini_keys_count": len(settings.gemini_api_keys),
        "embedding_model": settings.EMBEDDING_MODEL,
        "langgraph_enabled": True,
        "enabled_providers": settings.enabled_providers,
        "enabled_tools": len([k for k, v in settings.enabled_tools.items() if v]),
        "enabled_workflows": len([k for k, v in settings.enabled_workflows.items() if v]),
        "MAX_FILE_SIZE_MB": settings.MAX_FILE_SIZE_MB
    }