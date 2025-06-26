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

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager với complete system initialization
    """
    logger.info("🚀 Starting Complete Agentic RAG System...")
    
    try:
        # 1. Initialize database connections
        logger.info("📊 Initializing database connections...")
        from config.database import init_db
        await init_db()
        
        # 2. Initialize Milvus service (đã có)
        logger.info("🔍 Initializing Milvus service...")
        from services.vector.milvus_service import milvus_service
        await milvus_service.initialize()
        
        # 3. Initialize LLM provider manager
        logger.info("🧠 Initializing LLM providers...")
        from services.llm.provider_manager import llm_provider_manager
        await llm_provider_manager.initialize()
        
        # 4. Initialize tool manager
        logger.info("🛠️ Initializing tool manager...")
        from services.tools.tool_manager import tool_manager
        await tool_manager.initialize()
        
        # 5. Initialize intelligent orchestrator
        logger.info("🎯 Initializing intelligent orchestrator...")
        from services.orchestrator.intelligent_orchestrator import IntelligentOrchestrator
        orchestrator = IntelligentOrchestrator()
        # No explicit initialization needed - initialized on first use
        
        # 6. Initialize complete LangGraph workflow
        logger.info("🔄 Initializing complete LangGraph workflow...")
        from workflows.langgraph.complete_workflow import complete_rag_workflow
        await complete_rag_workflow.initialize()
        
        # 7. Initialize streaming services
        logger.info("🌊 Initializing streaming services...")
        from services.streaming.streaming_service import (
            streaming_orchestration_service,
            websocket_streaming_service
        )
        # Streaming services are initialized on demand
        
        # 8. System health check
        logger.info("⚕️ Performing system health check...")
        workflow_healthy = await complete_rag_workflow.health_check()
        milvus_healthy = await optimized_milvus_service.health_check()
        
        if not workflow_healthy:
            logger.warning("⚠️ Workflow health check failed")
        if not milvus_healthy:
            logger.warning("⚠️ Milvus health check failed")
        
        # 9. Log system configuration
        logger.info("📋 System configuration:")
        logger.info(f"  • Environment: {settings.ENV}")
        logger.info(f"  • Enabled LLM providers: {settings.get_enabled_providers()}")
        logger.info(f"  • Enabled agents: {settings.get_enabled_agents()}")
        logger.info(f"  • Enabled tools: {settings.get_enabled_tools()}")
        logger.info(f"  • Vector collections: {list(optimized_milvus_service.collection_configs.keys())}")
        logger.info(f"  • Orchestrator: {'Enabled' if settings.orchestrator.get('enabled', True) else 'Disabled'}")
        logger.info(f"  • Streaming: Enabled")
        logger.info(f"  • Multi-language support: vi, en, ja, ko")
        
        logger.info("✅ Complete Agentic RAG System started successfully!")
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Failed to start application: {e}")
        raise
    
    # Shutdown
    logger.info("🔄 Shutting down Complete Agentic RAG System...")
    
    try:
        # Close database connections
        from config.database import close_db
        await close_db()
        
        logger.info("✅ Application shutdown complete")
        
    except Exception as e:
        logger.error(f"❌ Error during shutdown: {e}")

# Create FastAPI app
app = FastAPI(
    title="Complete Agentic RAG System",
    description="""
    🚀 **Complete Agentic RAG System với Intelligent Orchestration**
    
    ## Tính năng chính:
    
    ### 🧠 Intelligent Orchestration
    - LLM-driven agent selection (không hardcode)
    - Dynamic task distribution
    - Smart tool selection
    - Conflict resolution giữa agents
    
    ### 🔍 Optimized Vector Search  
    - Collection riêng cho từng agent
    - Hybrid BM25 + Vector search
    - Chunking tự động theo file size
    - Reindexing tự động
    
    ### 🌊 Real-time Streaming
    - Server-Sent Events (SSE)
    - WebSocket support
    - Progress tracking
    - Batch processing
    
    ### 🌍 Multi-language Support
    - Vietnamese (default)
    - English, Japanese, Korean
    - Language-specific response formatting
    
    ### 🔐 Permission System
    - Department-level isolation
    - Document access control
    - Tool permissions
    - Audit trail
    
    ## Workflow Steps:
    1. **Query Analysis**: Phân tích và tinh chỉnh query
    2. **Task Distribution**: Phân phối nhiệm vụ cho agents  
    3. **Tool Selection**: Chọn tools phù hợp
    4. **RAG Retrieval**: Tìm kiếm documents với permission check
    5. **Document Evaluation**: Đánh giá và xếp hạng documents
    6. **Agent Execution**: Thực hiện agents song song
    7. **Conflict Resolution**: Giải quyết xung đột
    8. **Response Assembly**: Tạo response cuối với evidence
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
    
    # Log request completion với details
    status_emoji = "✅" if response.status_code < 400 else "❌"
    logger.info(
        f"{status_emoji} {request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.4f}s"
    )
    
    # Add performance headers
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-System-Version"] = "3.0.0"
    
    return response

# Include routers
app.include_router(api_router, prefix="/api/v1")
app.include_router(streaming_router, prefix="/api/v1/chat", tags=["Streaming"])

@app.get("/", tags=["System"])
async def root():
    """System information và capabilities"""
    try:
        from workflows.langgraph.workflow_graph import rag_workflow
        from services.vector.milvus_service import milvus_service
        
        # Get system status
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