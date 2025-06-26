from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import asyncio
import time

from config.database import DatabaseHealthCheck, test_connection
from config.settings import get_settings
from utils.logging import get_logger
from models.schemas import (
    BasicHealthResponse,
    DetailedHealthResponse,
    SystemStatusResponse,
    ReadinessResponse,
    LivenessResponse,
    ErrorResponse,
    HealthStatus,
    ComponentHealth,
    VectorDatabaseHealth,
    CacheHealth,
    EmbeddingHealth,
    WorkflowHealth,
    SystemConfiguration
)

router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()

@router.get("/", response_model=BasicHealthResponse)
async def health_check():
    """Basic health check endpoint"""
    try:
        return BasicHealthResponse(
            status=HealthStatus.HEALTHY,
            service="Agentic RAG",
            version="2.0.0",
            environment=settings.ENV,
            framework="FastAPI + LangGraph",
            timestamp=time.time()
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

@router.get("/detailed", response_model=DetailedHealthResponse)
async def detailed_health_check():
    """Comprehensive health check với tất cả services và system metrics"""
    try:
        from workflows.langgraph.workflow_graph import rag_workflow
        from services.vector.milvus_service import milvus_service
        from services.llm.provider_manager import llm_provider_manager
        
        db_health = await DatabaseHealthCheck.check_connectivity()
        milvus_health = await _check_milvus_health()
        redis_health = await _check_redis_health()
        embedding_health = await _check_embedding_health()
        workflow_health = await _check_workflow_health()
        llm_health = {}

        try:
            llm_health = await llm_provider_manager.health_check_all()
        except Exception as e:
            llm_health = {"error": str(e)}
        
        component_statuses = [
            db_health.get("status") == "healthy",
            milvus_health.status == HealthStatus.HEALTHY, 
            redis_health.status == HealthStatus.HEALTHY,
            embedding_health.status == HealthStatus.HEALTHY,
            workflow_health.status == HealthStatus.HEALTHY,
            any(llm_health.values()) if isinstance(llm_health, dict) and "error" not in llm_health else False
        ]
        
        overall_status = HealthStatus.HEALTHY if all(component_statuses) else HealthStatus.DEGRADED
        
        collection_stats = milvus_service.get_collection_stats()
        workflow_status = await rag_workflow.get_workflow_status()
        
        return DetailedHealthResponse(
            status=overall_status,
            timestamp=time.time(),
            system_version="2.0.0",
            environment=settings.ENV,
            components={
                "database": db_health,
                "vector_database": milvus_health,
                "cache": redis_health,
                "embedding": embedding_health,
                "workflow": workflow_health,
                "llm_providers": llm_health,
                "orchestrator": "healthy",
                "streaming": "healthy"
            },
            metrics={
                "vector_collections": len(collection_stats),
                "total_documents": sum(
                    stats.get("row_count", 0) for stats in collection_stats.values()
                    if isinstance(stats, dict)
                ),
                "enabled_providers": len(settings.get_enabled_providers()),
                "enabled_agents": len(settings.get_enabled_agents()),
                "enabled_tools": len(settings.get_enabled_tools())
            },
            collection_status=collection_stats,
            workflow_status=workflow_status,
            configuration=SystemConfiguration(
                enabled_providers=list(settings.enabled_providers.keys()),
                enabled_agents=list(settings.get_enabled_agents().keys()),
                enabled_tools=list(settings.get_enabled_tools().keys()),
                intelligent_orchestration=True,
                streaming_enabled=True,
                multi_language=True,
                hybrid_search=True,
                auto_reindexing=True,
                permission_system=True,
                langgraph_enabled=True
            )
        )
        
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return ErrorResponse(
            status=HealthStatus.ERROR,
            timestamp=time.time(),
            error=str(e)
        )

@router.get("/status", response_model=SystemStatusResponse)
async def system_status():
    """Detailed system status cho monitoring và debugging"""
    try:
        from workflows.langgraph.workflow_graph import rag_workflow
        from services.vector.milvus_service import milvus_service
        
        workflow_status = await rag_workflow.get_workflow_status()
        milvus_stats = milvus_service.get_collection_stats()
        
        return SystemStatusResponse(
            system={
                "name": "Complete Agentic RAG System",
                "version": "2.0.0",
                "environment": settings.ENV,
                "uptime": "N/A",
                "status": HealthStatus.OPERATIONAL,
                "timestamp": time.time()
            },
            workflow=workflow_status,
            vector_database={
                "service": "Milvus",
                "collections": milvus_stats,
                "total_collections": len(milvus_stats),
                "embedding_model": "BAAI/bge-m3",
                "embedding_dimensions": 1024
            },
            orchestration={
                "enabled": settings.orchestrator.get("enabled", True),
                "strategy": settings.orchestrator.get("strategy", "llm_orchestrator"),
                "max_agents_per_query": settings.orchestrator.get("max_agents_per_query", 3),
                "confidence_threshold": settings.orchestrator.get("confidence_threshold", 0.7)
            },
            agents={
                agent: {
                    "enabled": config.enabled,
                    "domain": config.domain,
                    "model": config.model,
                    "provider": config.provider
                }
                for agent, config in settings.agents.items()
                if hasattr(config, 'enabled')
            },
            tools={
                tool: {
                    "enabled": config.get("enabled", False),
                    "config": config.get("config", {})
                }
                for tool, config in settings.tools.items()
            },
            performance={
                "chunking": "Auto-optimized based on file size",
                "search": "Hybrid BM25 + Vector",
                "reindexing": "Automatic on demand",
                "streaming": "Real-time SSE + WebSocket",
                "caching": "Redis-based"
            },
            languages=["vi", "en", "ja", "ko"],
            last_updated=time.time()
        )
        
    except Exception as e:
        logger.error(f"Status endpoint failed: {e}")
        return ErrorResponse(
            status=HealthStatus.ERROR,
            timestamp=time.time(),
            error=str(e)
        )

@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check():
    """Kubernetes readiness probe"""
    try:
        db_connected = await test_connection()
        
        if not db_connected:
            raise HTTPException(status_code=503, detail="Database not ready")
        
        return ReadinessResponse(
            status=HealthStatus.READY,
            timestamp=time.time()
        )
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")

@router.get("/live", response_model=LivenessResponse)
async def liveness_check():
    """Kubernetes liveness probe"""
    return LivenessResponse(
        status=HealthStatus.ALIVE,
        timestamp=time.time()
    )

async def _check_milvus_health() -> VectorDatabaseHealth:
    """Check Milvus vector database health"""
    try:
        from services.vector.milvus_service import milvus_service
        
        is_healthy = await milvus_service.health_check()
        
        return VectorDatabaseHealth(
            status=HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY,
            host=settings.MILVUS_HOST,
            port=settings.MILVUS_PORT,
            collection=settings.MILVUS_COLLECTION
        )
        
    except Exception as e:
        logger.warning(f"Milvus health check failed: {e}")
        return VectorDatabaseHealth(
            status=HealthStatus.ERROR,
            error=str(e),
            host=settings.MILVUS_HOST,
            port=settings.MILVUS_PORT
        )

async def _check_redis_health() -> CacheHealth:
    """Check Redis health"""
    try:
        import redis.asyncio as redis
        
        client = redis.from_url(settings.redis_url)
        await client.ping()
        await client.close()
        
        return CacheHealth(
            status=HealthStatus.HEALTHY,
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB
        )
        
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return CacheHealth(
            status=HealthStatus.ERROR,
            error=str(e),
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT
        )

async def _check_embedding_health() -> EmbeddingHealth:
    """Check embedding service health"""
    try:
        from services.embedding.embedding_service import embedding_service
        
        is_healthy = await embedding_service.health_check()
        
        return EmbeddingHealth(
            status=HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY,
            model=settings.EMBEDDING_MODEL,
            device=settings.EMBEDDING_MODEL_DEVICE,
            dimensions=settings.EMBEDDING_DIMENSIONS
        )
        
    except Exception as e:
        logger.warning(f"Embedding service health check failed: {e}")
        return EmbeddingHealth(
            status=HealthStatus.ERROR,
            error=str(e),
            model=settings.EMBEDDING_MODEL
        )

async def _check_workflow_health() -> WorkflowHealth:
    """Check LangGraph workflow health"""
    try:
        from workflows.langgraph.workflow_graph import rag_workflow
        
        workflow_healthy = await rag_workflow.health_check()
        
        return WorkflowHealth(
            status=HealthStatus.HEALTHY if workflow_healthy else HealthStatus.UNHEALTHY,
            framework="LangGraph",
            agents_enabled=len(settings.get_enabled_agents()),
            orchestrator_enabled=settings.orchestrator.get("enabled", True)
        )
        
    except Exception as e:
        logger.warning(f"Workflow health check failed: {e}")
        return WorkflowHealth(
            status=HealthStatus.ERROR,
            error=str(e),
            framework="LangGraph"
        )
