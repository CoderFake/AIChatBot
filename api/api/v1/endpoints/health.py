from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import asyncio

from config.database import DatabaseHealthCheck, test_connection
from config.settings import get_settings
from utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()

@router.get("/", response_model=Dict[str, Any])
async def health_check():
    """Basic health check endpoint"""
    try:
        return {
            "status": "healthy",
            "service": "Agentic RAG API",
            "version": "2.0.0",
            "environment": settings.ENV,
            "framework": "FastAPI + LangGraph"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

@router.get("/detailed", response_model=Dict[str, Any])
async def detailed_health_check():
    """Detailed health check với tất cả services"""
    try:
        # Check database connectivity
        db_health = await DatabaseHealthCheck.check_connectivity()
        
        # Check vector database (Milvus)
        milvus_health = await _check_milvus_health()
        
        # Check Redis (if available)
        redis_health = await _check_redis_health()
        
        # Check embedding service
        embedding_health = await _check_embedding_health()
        
        # Overall status
        all_healthy = all([
            db_health.get("status") == "healthy",
            milvus_health.get("status") == "healthy",
            redis_health.get("status") == "healthy",
            embedding_health.get("status") == "healthy"
        ])
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "timestamp": asyncio.get_event_loop().time(),
            "environment": settings.ENV,
            "services": {
                "database": db_health,
                "vector_database": milvus_health,
                "cache": redis_health,
                "embedding": embedding_health
            },
            "configuration": {
                "enabled_providers": settings.enabled_providers,
                "enabled_tools_count": len([k for k, v in settings.enabled_tools.items() if v]),
                "langgraph_enabled": True,
                "multi_tenant": settings.ENABLE_MULTI_TENANT
            }
        }
        
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return {
            "status": "error",
            "timestamp": asyncio.get_event_loop().time(),
            "error": str(e)
        }

@router.get("/ready", response_model=Dict[str, Any])
async def readiness_check():
    """Kubernetes readiness probe"""
    try:
        # Check critical services only
        db_connected = await test_connection()
        
        if not db_connected:
            raise HTTPException(status_code=503, detail="Database not ready")
        
        return {
            "status": "ready",
            "timestamp": asyncio.get_event_loop().time()
        }
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")

@router.get("/live", response_model=Dict[str, Any])
async def liveness_check():
    """Kubernetes liveness probe"""
    return {
        "status": "alive",
        "timestamp": asyncio.get_event_loop().time()
    }

async def _check_milvus_health() -> Dict[str, Any]:
    """Check Milvus vector database health"""
    try:
        from services.vector.milvus_service import milvus_service
        
        # Attempt to get collection info
        is_healthy = await milvus_service.health_check()
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "host": settings.MILVUS_HOST,
            "port": settings.MILVUS_PORT,
            "collection": settings.MILVUS_COLLECTION
        }
        
    except Exception as e:
        logger.warning(f"Milvus health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "host": settings.MILVUS_HOST,
            "port": settings.MILVUS_PORT
        }

async def _check_redis_health() -> Dict[str, Any]:
    """Check Redis health"""
    try:
        import redis.asyncio as redis
        
        client = redis.from_url(settings.redis_url)
        await client.ping()
        await client.close()
        
        return {
            "status": "healthy",
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
            "db": settings.REDIS_DB
        }
        
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT
        }

async def _check_embedding_health() -> Dict[str, Any]:
    """Check embedding service health"""
    try:
        from services.embedding.embedding_service import embedding_service
        
        # Check if embedding service is initialized
        is_healthy = await embedding_service.health_check()
        
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "model": settings.EMBEDDING_MODEL,
            "device": settings.EMBEDDING_MODEL_DEVICE,
            "dimensions": settings.EMBEDDING_DIMENSIONS
        }
        
    except Exception as e:
        logger.warning(f"Embedding service health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "model": settings.EMBEDDING_MODEL
        }
