from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import time

from config.settings import get_settings
from utils.logging import get_logger
from models.schemas.responses.health import (
    BasicHealthResponse,
    ReadinessResponse,
    LivenessResponse,
    ErrorResponse,
    HealthStatus,
)
from config.database import test_connection

router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()


@router.get("/", response_model=BasicHealthResponse)
async def health_check():
    """Basic health check endpoint"""
    try:
        return BasicHealthResponse(
            status=HealthStatus.HEALTHY,
            service=settings.APP_NAME,
            version=settings.APP_VERSION,
            environment=settings.ENV,
            framework="FastAPI",
            timestamp=time.time(),
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check():
    try:
        db_connected = await test_connection()
        if not db_connected:
            raise HTTPException(status_code=503, detail="Database not ready")
        return ReadinessResponse(status=HealthStatus.READY, timestamp=time.time())
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Service not ready")


@router.get("/live", response_model=LivenessResponse)
async def liveness_check():
    """Kubernetes liveness probe"""
    return LivenessResponse(status=HealthStatus.ALIVE, timestamp=time.time())
