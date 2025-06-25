"""
Main FastAPI application với integrated configuration management
Real-time config changes và auto-reload components
"""

import time
import uvicorn
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from services.config.config_manager import config_manager
from api.v1.router import api_router
from api.v1.endpoints.admin import router as admin_router
from core.exceptions import setup_exception_handlers
from utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    Handles startup và shutdown với config management
    """
    # Startup
    logger.info("Starting Agentic RAG API with real-time configuration...")
    
    try:
        # Initialize configuration manager first
        await config_manager.initialize()
        logger.info("Configuration manager initialized")
        
        # Initialize database connections
        from config.database import init_db
        await init_db()
        logger.info("Database initialized")
        
        # Initialize vector database
        from services.vector.vector_service import VectorService
        vector_service = VectorService()
        await vector_service.initialize()
        logger.info("Vector database initialized")
        
        # Initialize LLM provider manager
        from services.llm.provider_manager import llm_provider_manager
        await llm_provider_manager.initialize()
        logger.info("LLM providers initialized")
        
        # Initialize tool service
        from services.tools.tool_service import ToolService
        tool_service = ToolService()
        await tool_service.initialize()
        logger.info("Tool service initialized")
        
        # Initialize RAG workflow (will auto-subscribe to config changes)
        from workflows.langgraph.workflow_graph import rag_workflow
        await rag_workflow.initialize()
        logger.info("RAG workflow initialized with config management")
        
        logger.info(f"Agentic RAG API started successfully! Environment: {settings.ENV}")
        logger.info(f"Configuration: {len(settings.get_enabled_providers())} providers, "
                   f"{len(settings.get_enabled_tools())} tools, "
                   f"{len(settings.get_enabled_agents())} agents")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    
    # Shutdown
    logger.info("Shutting down Agentic RAG API...")
    
    try:
        # Stop configuration monitoring
        await config_manager.stop_monitoring()
        logger.info("Configuration monitoring stopped")
        
        # Close database connections
        from config.database import close_db
        await close_db()
        logger.info("Database connections closed")
        
        logger.info("Application shutdown complete")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# Create FastAPI app với lifespan management
app = FastAPI(
    title=settings.APP_NAME,
    description="Agentic RAG System với Real-time Configuration Management",
    version="2.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan
)

# Setup exception handlers
setup_exception_handlers(app)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests với performance tracking"""
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.4f}s"
    )
    
    # Add processing time header
    response.headers["X-Process-Time"] = str(process_time)
    
    return response

app.include_router(api_router, prefix="/api/v1")

app.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin Configuration"])


@app.get("/", tags=["System"])
async def root():
    """System information endpoint"""
    try:
        await config_manager.get_current_config()
        
        return {
            "name": settings.APP_NAME,
            "version": "2.0.0",
            "status": "running",
            "framework": "FastAPI + LangGraph",
            "features": [
                "Real-time Configuration Management",
                "Multi-Provider LLM Support", 
                "Dynamic Tool Loading",
                "Intelligent Agent Orchestration",
                "Auto-Reload Components"
            ],
            "environment": settings.ENV,
            "configuration": {
                "providers": len(settings.get_enabled_providers()),
                "tools": len(settings.get_enabled_tools()),
                "agents": len(settings.get_enabled_agents()),
                "orchestrator": settings.orchestrator.get("enabled", True)
            }
        }
        
    except Exception as e:
        logger.error(f"Root endpoint error: {e}")
        return {
            "name": settings.APP_NAME,
            "version": "2.0.0",
            "status": "running",
            "error": "Could not load configuration details"
        }

@app.get("/health", tags=["System"])
async def health_check():
    """Comprehensive health check endpoint"""
    try:
        from workflows.langgraph.workflow_graph import rag_workflow
        from services.llm.provider_manager import llm_provider_manager
        from services.tools.tool_service import ToolService
        from config.database import test_connection
        
        workflow_healthy = await rag_workflow.health_check()
        db_healthy = await test_connection()
        
        llm_health = {}
        try:
            llm_health = await llm_provider_manager.health_check_all()
        except Exception as e:
            llm_health = {"error": str(e)}
        
        # Tool service health
        tool_health = True
        try:
            tool_service = ToolService()
            tool_health = tool_service._initialized
        except Exception:
            tool_health = False
        
        # Overall health
        component_health = [
            workflow_healthy,
            db_healthy,
            any(llm_health.values()) if isinstance(llm_health, dict) else False,
            tool_health
        ]
        
        overall_status = "healthy" if all(component_health) else "degraded"
        
        return {
            "status": overall_status,
            "timestamp": time.time(),
            "components": {
                "workflow": "healthy" if workflow_healthy else "unhealthy",
                "database": "healthy" if db_healthy else "unhealthy", 
                "llm_providers": llm_health,
                "tools": "healthy" if tool_health else "unhealthy",
                "config_manager": "healthy" 
            },
            "configuration": {
                "auto_reload": True,
                "real_time_config": True,
                "enabled_providers": settings.get_enabled_providers(),
                "enabled_tools": settings.get_enabled_tools(),
                "enabled_agents": settings.get_enabled_agents()
            }
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "timestamp": time.time(),
            "error": str(e)
        }

@app.get("/config/live", tags=["Configuration"])
async def get_live_configuration():
    """
    Get live configuration status
    Shows real-time state of all components
    """
    try:
        from workflows.langgraph.workflow_graph import rag_workflow
        
        workflow_config = await rag_workflow.get_configuration_status()
        system_config = await config_manager.get_current_config()
        
        return {
            "status": "live",
            "timestamp": time.time(),
            "workflow_status": workflow_config,
            "system_config": system_config,
            "config_manager": {
                "monitoring": True,
                "subscribers": len(config_manager._subscribers),
                "change_queue_size": config_manager._change_queue.qsize()
            }
        }
        
    except Exception as e:
        logger.error(f"Live configuration check failed: {e}")
        return {
            "status": "error",
            "timestamp": time.time(),
            "error": str(e)
        }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )