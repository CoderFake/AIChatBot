from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional, Union
from enum import Enum

class HealthStatus(str, Enum):
    """Enum cho các trạng thái health"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    ERROR = "error"
    READY = "ready"
    ALIVE = "alive"
    OPERATIONAL = "operational"

class BasicHealthResponse(BaseModel):
    """Basic health check response"""
    status: HealthStatus
    service: str
    version: str
    environment: str
    framework: str
    timestamp: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "service": "Agentic RAG",
                "version": "2.0.0",
                "environment": "development",
                "framework": "FastAPI + LangGraph",
                "timestamp": 1699123456.789
            }
        }

class ComponentHealth(BaseModel):
    """Health status của một component"""
    status: HealthStatus
    host: Optional[str] = None
    port: Optional[int] = None
    error: Optional[str] = None
    
class DatabaseHealth(ComponentHealth):
    """Database health response"""
    connection_pool_size: Optional[int] = None
    active_connections: Optional[int] = None
    
class VectorDatabaseHealth(ComponentHealth):
    """Vector database (Milvus) health response"""
    collection: Optional[str] = None
    collections_count: Optional[int] = None
    
class CacheHealth(ComponentHealth):
    """Redis cache health response"""
    db: Optional[int] = None
    memory_usage: Optional[str] = None
    
class EmbeddingHealth(ComponentHealth):
    """Embedding service health response"""
    model: Optional[str] = None
    device: Optional[str] = None
    dimensions: Optional[int] = None
    
class WorkflowHealth(ComponentHealth):
    """LangGraph workflow health response"""
    framework: Optional[str] = None
    agents_enabled: Optional[int] = None
    orchestrator_enabled: Optional[bool] = None

class SystemMetrics(BaseModel):
    """System metrics information"""
    vector_collections: int
    total_documents: int
    enabled_providers: int
    enabled_agents: int
    enabled_tools: int

class SystemConfiguration(BaseModel):
    """System configuration information"""
    enabled_providers: List[str]
    enabled_agents: List[str]
    enabled_tools: List[str]
    intelligent_orchestration: bool
    streaming_enabled: bool
    multi_language: bool
    hybrid_search: bool
    auto_reindexing: bool
    permission_system: bool
    langgraph_enabled: bool

class DetailedHealthResponse(BaseModel):
    """Comprehensive health check response"""
    status: HealthStatus
    timestamp: float
    system_version: str
    environment: str
    
    components: Dict[str, Union[ComponentHealth, Dict[str, Any]]] = Field(
        description="Health status của tất cả components"
    )
    metrics: SystemMetrics
    collection_status: Dict[str, Any]
    workflow_status: Dict[str, Any]
    configuration: SystemConfiguration
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": 1699123456.789,
                "system_version": "2.0.0",
                "environment": "development",
                "components": {
                    "database": {"status": "healthy"},
                    "vector_database": {"status": "healthy", "host": "localhost", "port": 19530},
                    "cache": {"status": "healthy", "host": "localhost", "port": 6379},
                    "embedding": {"status": "healthy", "model": "BAAI/bge-m3"},
                    "workflow": {"status": "healthy", "framework": "LangGraph"}
                },
                "metrics": {
                    "vector_collections": 4,
                    "total_documents": 1250,
                    "enabled_providers": 2,
                    "enabled_agents": 4,
                    "enabled_tools": 8
                },
                "configuration": {
                    "intelligent_orchestration": True,
                    "streaming_enabled": True,
                    "multi_language": True
                }
            }
        }

class SystemInfo(BaseModel):
    """System information"""
    name: str
    version: str
    environment: str
    uptime: str
    status: HealthStatus
    timestamp: float

class VectorDatabaseInfo(BaseModel):
    """Vector database detailed information"""
    service: str
    collections: Dict[str, Any]
    total_collections: int
    embedding_model: str
    embedding_dimensions: int

class OrchestrationInfo(BaseModel):
    """Orchestration configuration"""
    enabled: bool
    strategy: str
    max_agents_per_query: int
    confidence_threshold: float

class AgentInfo(BaseModel):
    """Agent configuration"""
    enabled: bool
    domain: str
    model: str
    provider: str

class ToolInfo(BaseModel):
    """Tool configuration"""
    enabled: bool
    config: Dict[str, Any]

class PerformanceInfo(BaseModel):
    """Performance configuration"""
    chunking: str
    search: str
    reindexing: str
    streaming: str
    caching: str

class SystemStatusResponse(BaseModel):
    """Detailed system status response"""
    system: SystemInfo
    workflow: Dict[str, Any]
    vector_database: VectorDatabaseInfo
    orchestration: OrchestrationInfo
    agents: Dict[str, AgentInfo]
    tools: Dict[str, ToolInfo]
    performance: PerformanceInfo
    languages: List[str]
    last_updated: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "system": {
                    "name": "Complete Agentic RAG System",
                    "version": "2.0.0",
                    "environment": "development",
                    "status": "operational",
                    "timestamp": 1699123456.789
                },
                "vector_database": {
                    "service": "Milvus",
                    "total_collections": 4,
                    "embedding_model": "BAAI/bge-m3"
                },
                "orchestration": {
                    "enabled": True,
                    "strategy": "llm_orchestrator"
                },
                "languages": ["vi", "en", "ja", "ko"]
            }
        }

class ReadinessResponse(BaseModel):
    """Kubernetes readiness probe response"""
    status: HealthStatus
    timestamp: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "ready",
                "timestamp": 1699123456.789
            }
        }

class LivenessResponse(BaseModel):
    """Kubernetes liveness probe response"""
    status: HealthStatus
    timestamp: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "alive",
                "timestamp": 1699123456.789
            }
        }

class ErrorResponse(BaseModel):
    """Error response cho health checks"""
    status: HealthStatus
    timestamp: float
    error: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "error",
                "timestamp": 1699123456.789,
                "error": "Database connection failed"
            }
        }
