import time
import uvicorn
import os
import asyncio

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

from config.settings import get_settings
from api.v1.router import api_router
from core.exceptions import setup_exception_handlers
from utils.logging import get_logger

logger = get_logger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="Agentic RAG System với LangGraph",
    version="2.0.0",
    docs_url=None if not settings.ENABLE_DOCS else "/docs",
    redoc_url=None if not settings.ENABLE_DOCS else "/redoc",
    openapi_url=None if not settings.ENABLE_DOCS else "/openapi.json"
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

start_time = time.time()

# Include API routes
app.include_router(api_router, prefix="/api/v1")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware to log requests"""
    start_time_req = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time_req
    
    logger.info(
        f"{request.method} {request.url.path} "
        f"- Time: {process_time:.4f}s "
        f"- Status: {response.status_code}"
    )
    
    return response

@app.on_event("startup")
async def startup():
    """Initialize services on startup"""
    logger.info("Starting Agentic RAG API with LangGraph...")
    
    # Initialize database connections
    from config.database import init_db
    await init_db()
    logger.info("Database initialized")
    
    # Initialize vector database
    from services.vector.milvus_service import milvus_service
    await milvus_service.initialize()
    logger.info("Milvus vector database initialized")
    
    # Initialize embedding service
    from services.embedding.embedding_service import embedding_service
    await embedding_service.initialize()
    logger.info("Embedding service initialized")
    
    # Initialize LangGraph workflow
    from workflows.langgraph.workflow_graph import rag_workflow
    await rag_workflow.initialize()
    logger.info("LangGraph RAG workflow initialized")
    
    # Create necessary directories
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs("/app/data", exist_ok=True)
    
    logger.info(f"Agentic RAG API started successfully. Environment: {settings.ENV}")

@app.on_event("shutdown")
async def shutdown():
    """Cleanup on shutdown"""
    logger.info("Shutting down Agentic RAG API...")
    
    # Close database connections
    from config.database import close_db
    await close_db()
    logger.info("Database connections closed")
    
    logger.info("Application shutdown complete")

@app.get("/", tags=["System"])
async def root():
    """System check endpoint"""
    return {
        "name": settings.APP_NAME,
        "version": "2.0.0",
        "status": "running",
        "framework": "FastAPI + LangGraph",
        "uptime": f"{(time.time() - start_time):.2f} s"
    }

@app.get("/health", tags=["System"])
async def health_check():
    """System health check endpoint"""
    return {
        "status": "healthy",
        "uptime": f"{(time.time() - start_time):.2f} s",
        "environment": settings.ENV,
        "services": {
            "database": "connected",
            "vector_db": "connected", 
            "embedding": "loaded",
            "langgraph": "initialized"
        }
    }

if settings.ENABLE_DOCS:
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        """Swagger UI endpoint"""
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Swagger UI",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url="/static/swagger-ui-bundle.js",
            swagger_css_url="/static/swagger-ui.css",
        )

    @app.get("/redoc", include_in_schema=False)
    async def redoc_html():
        """ReDoc endpoint"""
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - ReDoc",
            redoc_js_url="/static/redoc.standalone.js",
        )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info"
    )
