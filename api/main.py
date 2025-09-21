import time
import uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from config.settings import get_settings
from api.v1.router import api_router
from core.exceptions import setup_exception_handlers
from utils.logging import get_logger
from prometheus_fastapi_instrumentator import Instrumentator

logger = get_logger(__name__)
settings = get_settings()


async def _init_db() -> None:
    """Initialize database connections."""
    logger.info("Initializing database connections...")
    from config.database import init_db

    await init_db()


async def _sync_registries() -> None:
    """Sync provider/model/tool registries into the database on startup."""
    try:
        from config.database import get_db_context
        from services.llm.provider_service import ProviderService
        from services.llm.provider_manager import LLMProviderManager
        from services.tools.tool_service import ToolService
        from services.bootstrap.seed_maintainer import seed_global_maintainer, seed_permissions
        from services.cache.cache_manager import cache_manager

        await cache_manager.initialize()
        logger.info("Cache manager initialized globally")

        import services.orchestrator.orchestrator as orch_module
        orch_module.global_cache_manager = cache_manager

        global_provider_manager = LLMProviderManager()
        await global_provider_manager.initialize()
        orch_module.global_provider_manager = global_provider_manager
        logger.info("LLM Provider Manager initialized globally")

        async with get_db_context() as session:
            await seed_global_maintainer(session)
            await seed_permissions(session)

            provider_service = ProviderService(session)
            await provider_service.initialize()

            tool_service = ToolService(session)
            await tool_service.initialize()

        logger.info("Registry sync completed (providers/models/tools)")
    except Exception as e:
        logger.error(f"Failed to sync registries: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager with minimal, robust initialization."""
    logger.info(" Starting AIChatBot API...")

    try:
        await _init_db()
        logger.info("Database initialized")

        await _sync_registries()

        yield

    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise

    logger.info("Shutting down AIChatBot API...")

    try:
        from services.messaging.kafka_service import kafka_service
        from config.database import close_db

        # Cleanup Kafka service
        await kafka_service.cleanup()

        # Close database
        await close_db()

        logger.info("Application shutdown complete")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


app = FastAPI(
    title=settings.APP_NAME,
    description="API for AIChatBot",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan,
)

setup_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Metrics
Instrumentator().instrument(app).expose(app, include_in_schema=False, endpoint="/metrics")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with performance tracking"""
    start_time = time.time()
    logger.info(f"{request.method} {request.url.path} - Started")

    response = await call_next(request)

    process_time = time.time() - start_time
    status_emoji = "Success" if response.status_code < 400 else "Failed"
    logger.info(
        f"{status_emoji} {request.method} {request.url.path} - "
        f"Status: {response.status_code} - Time: {process_time:.4f}s"
    )

    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-System-Version"] = settings.APP_VERSION

    return response

# Routers
app.include_router(api_router, prefix="/api/v1")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT or 15000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
        access_log=True,
    )