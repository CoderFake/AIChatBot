import time
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from api.v1.router import api_router
from api.v1.endpoints.streaming import router as streaming_router
from core.exceptions import setup_exception_handlers
from utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def _init_db() -> None:
    """Initialize database connections."""
    logger.info("Initializing database connections...")
    from config.database import init_db

    await init_db()


async def _init_milvus():
    """Initialize Milvus vector service."""
    logger.info("🔍 Initializing Milvus service...")
    from services.vector.milvus_service import milvus_service

    await milvus_service.initialize()
    return milvus_service


async def _init_llm_providers() -> None:
    """Initialize LLM providers using database configuration."""
    logger.info("🧠 Initializing LLM providers...")
    from services.llm.provider_manager import llm_provider_manager
    from config.database import get_db_session

    db_session = next(get_db_session())
    try:
        await llm_provider_manager.initialize(db_session=db_session)
    finally:
        db_session.close()


async def _init_tool_manager() -> None:
    """Initialize tool manager."""
    logger.info("Initializing tool manager...")
    from services.tools.tool_manager import tool_manager

    await tool_manager.initialize()


async def _init_orchestrator():
    """Initialize intelligent orchestrator."""
    logger.info("Initializing intelligent orchestrator...")
    from services.orchestrator.intelligent_orchestrator import (
        IntelligentOrchestrator,
    )

    orchestrator = IntelligentOrchestrator()
    return orchestrator


async def _init_workflow():
    """Initialize LangGraph workflow."""
    logger.info("Initializing complete LangGraph workflow...")
    from workflows.langgraph.complete_workflow import complete_rag_workflow

    await complete_rag_workflow.initialize()
    return complete_rag_workflow


async def _init_streaming() -> None:
    """Prepare streaming services."""
    logger.info("Initializing streaming services...")
    from services.streaming.streaming_service import (
        streaming_orchestration_service,
        websocket_streaming_service,
    )

    # Streaming services initialize on demand; this import ensures availability
    _ = (streaming_orchestration_service, websocket_streaming_service)


async def _perform_health_check(workflow, milvus):
    """Run health checks for major components."""
    logger.info("⚕️ Performing system health check...")
    workflow_healthy = await workflow.health_check()
    milvus_healthy = await milvus.health_check()

    if not workflow_healthy:
        logger.warning("Workflow health check failed")
    if not milvus_healthy:
        logger.warning("Milvus health check failed")


def _log_system_config(milvus) -> None:
    """Log system configuration details."""
    logger.info("System configuration:")
    logger.info(f"  • Environment: {settings.ENV}")
    logger.info(f"  • Enabled LLM providers: {settings.get_enabled_providers()}")
    logger.info(f"  • Enabled agents: {settings.get_enabled_agents()}")
    logger.info(f"  • Enabled tools: {settings.get_enabled_tools()}")
    logger.info(
        f"  • Vector collections: {list(milvus.collection_configs.keys())}"
    )
    logger.info(
        f"  • Orchestrator: {'Enabled' if settings.orchestrator.get('enabled', True) else 'Disabled'}"
    )
    logger.info("  • Streaming: Enabled")
    logger.info("  • Multi-language support: vi, en, ja, ko")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with modular initialization."""
    logger.info("🚀 Starting Complete Agentic RAG System...")

    try:
        await _init_db()
        logger.info("🚀 Using registry-based configuration (no complex sync needed)")

        milvus = await _init_milvus()
        await _init_llm_providers()
        await _init_tool_manager()
        _ = await _init_orchestrator()
        workflow = await _init_workflow()
        await _init_streaming()
        await _perform_health_check(workflow, milvus)
        _log_system_config(milvus)

        logger.info("Complete Agentic RAG System started successfully!")

        yield

    except Exception as e:
        logger.error(f"❌ Failed to start application: {e}")
        raise

    logger.info("Shutting down Complete Agentic RAG System...")

    try:
        from config.database import close_db

        await close_db()
        logger.info("✅ Application shutdown complete")

    except Exception as e:
        logger.error(f"❌ Error during shutdown: {e}")

app = FastAPI(
    title="Complete Agentic RAG System",
    description="""
    Agentic RAG System 
    """,
    version="3.0.0",
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

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests với detailed performance tracking"""
    start_time = time.time()
    
    # Log request start
    logger.info(f"📥 {request.method} {request.url.path} - Started")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    
    status_emoji = "✅" if response.status_code < 400 else "❌"
    logger.info(
        f"{status_emoji} {request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.4f}s"
    )
    
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-System-Version"] = "3.0.0"
    
    return response

app.include_router(api_router, prefix="/api/v1")
app.include_router(streaming_router, prefix="/api/v1/chat", tags=["Streaming"])

@app.get("/", tags=["System"])
async def root():
    """System information và capabilities"""
    try:
        from workflows.langgraph.workflow_graph import rag_workflow
        from services.vector.milvus_service import milvus_service
        
        workflow_status = await rag_workflow.get_workflow_status()
        milvus_stats = milvus_service.get_collection_stats()
        
        return {
            "name": "Complete Agentic RAG System",
            "version": "2.0.0",
            "status": "operational",
            "framework": "FastAPI + LangGraph",
            
            "capabilities": {
                "intelligent_orchestration": "LLM-driven decision making",
                "multi_agent_system": "Specialized domain agents",
                "streaming_responses": "Real-time SSE và WebSocket",
                "hybrid_search": "BM25 + Vector search", 
                "multi_language": "vi, en, ja, ko support",
                "permission_system": "Department-level access control",
                "auto_optimization": "Self-tuning performance"
            },
            
            "system_config": {
                "environment": settings.ENV,
                "providers": settings.get_enabled_providers(),
                "agents": settings.get_enabled_agents(),
                "tools": settings.get_enabled_tools(),
                "collections": list(milvus_stats.keys()),
                "orchestrator_enabled": settings.orchestrator.get("enabled", True),
                "workflow_initialized": workflow_status["initialized"]
            },
            
            "api_endpoints": {
                "streaming": "/api/v1/chat/stream",
                "document": "/api/v1/documents/",
                "health_check": "/api/v1/health",
                "system_status": "/api/v1/health/detailed"
            },
            
            "architecture": {
                "orchestration": "Intelligent LLM-based routing",
                "agents": "Domain-specific specialists",
                "vector_db": "Milvus với per-agent collections",
                "embedding": "BAAI/bge-m3 multilingual",
                "streaming": "SSE + WebSocket real-time",
                "workflow": "LangGraph state management"
            }
        }
        
    except Exception as e:
        logger.error(f"Root endpoint error: {e}")
        return {
            "name": "Complete Agentic RAG System",
            "version": "2.0.0",
            "status": "running",
            "error": "Could not load full system status"
        }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
        access_log=True
    )