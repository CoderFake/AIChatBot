from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, Any, List, Optional
from utils.datetime_utils import CustomDateTime as datetime


from workflows.langgraph.workflow_graph import rag_workflow
from schemas import QueryRequest, QueryResponse, HealthResponse
from services.llm.provider_manager import llm_provider_manager
from services.tools.tool_service import ToolService
from services.vector.vector_service import VectorService
from config.settings import get_settings
from utils.logging import get_logger, log_performance

router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()

@router.post("/rag", response_model=QueryResponse)
@log_performance()
async def process_rag_query(
    request: QueryRequest,
    background_tasks: BackgroundTasks
) -> QueryResponse:
    """
    Main RAG query endpoint
    Business logic delegated to workflow service
    """
    try:
        logger.info(f"Processing RAG query: {request.query[:100]}...")
        
        # Validate workflow is ready
        if not await rag_workflow.health_check():
            logger.info("Initializing RAG workflow...")
            await rag_workflow.initialize()
        
        # Process through workflow
        result = await rag_workflow.process_query(
            query=request.query,
            user_id=request.user_id,
            session_id=request.session_id,
            language=request.language,
            conversation_history=request.conversation_history
        )
        
        # Log successful query in background
        background_tasks.add_task(
            _log_query_completion,
            request.query,
            request.user_id,
            result["workflow_id"],
            result["processing_time"]
        )
        
        return QueryResponse(
            response=result["response"],
            sources=result["sources"],
            confidence=result["confidence"],
            workflow_id=result["workflow_id"],
            processing_time=result["processing_time"],
            metadata=result["metadata"]
        )
        
    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {str(e)}"
        )

@router.get("/health", response_model=HealthResponse)
async def get_system_health() -> HealthResponse:
    """
    Comprehensive system health check
    """
    try:
        # Check all major components
        workflow_health = await rag_workflow.health_check()
        
        # Check LLM providers
        llm_health = {}
        try:
            if not llm_provider_manager._initialized:
                await llm_provider_manager.initialize()
            llm_health = await llm_provider_manager.health_check_all()
        except Exception as e:
            logger.warning(f"LLM health check failed: {e}")
            llm_health = {"error": str(e)}
        
        # Check vector service
        vector_health = {}
        try:
            vector_service = VectorService()
            vector_health["status"] = "healthy" if await vector_service.health_check() else "unhealthy"
        except Exception as e:
            vector_health = {"status": "error", "error": str(e)}
        
        # Check tool service
        tool_health = {}
        try:
            tool_service = ToolService()
            if not tool_service._initialized:
                await tool_service.initialize()
            available_tools = tool_service.get_available_tools()
            tool_health = {
                "status": "healthy",
                "available_tools": len(available_tools),
                "tools": available_tools
            }
        except Exception as e:
            tool_health = {"status": "error", "error": str(e)}
        
        # Determine overall status
        component_statuses = [
            workflow_health,
            all(llm_health.values()) if isinstance(llm_health, dict) and "error" not in llm_health else False,
            vector_health.get("status") == "healthy",
            tool_health.get("status") == "healthy"
        ]
        
        overall_status = "healthy" if all(component_statuses) else "degraded"
        
        return HealthResponse(
            status=overall_status,
            components={
                "workflow": {"status": "healthy" if workflow_health else "unhealthy"},
                "llm_providers": llm_health,
                "vector_database": vector_health,
                "tools": tool_health,
                "configuration": {
                    "enabled_providers": settings.get_enabled_providers(),
                    "enabled_agents": settings.get_enabled_agents(),
                    "enabled_tools": settings.get_enabled_tools()
                }
            },
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="error",
            components={"error": str(e)},
            timestamp=datetime.now().isoformat()
        )

@router.get("/config")
async def get_system_configuration() -> Dict[str, Any]:
    """
    Get current system configuration
    Useful for debugging and admin interface
    """
    try:
        return {
            "providers": {
                name: {
                    "enabled": config.enabled,
                    "models": config.models,
                    "default_model": config.default_model
                }
                for name, config in settings.llm_providers.items()
            },
            "agents": {
                name: {
                    "enabled": config.enabled,
                    "domain": config.domain,
                    "capabilities": config.capabilities,
                    "tools": config.tools,
                    "model": config.model
                }
                for name, config in settings.agents.items()
            },
            "tools": settings.tools,
            "workflow": {
                "max_iterations": settings.workflow.max_iterations,
                "timeout_seconds": settings.workflow.timeout_seconds,
                "enable_reflection": settings.workflow.enable_reflection,
                "enable_semantic_routing": settings.workflow.enable_semantic_routing,
                "enable_document_grading": settings.workflow.enable_document_grading,
                "checkpointer_type": settings.workflow.checkpointer_type
            },
            "orchestrator": settings.orchestrator,
            "rag": settings.rag
        }
        
    except Exception as e:
        logger.error(f"Failed to get configuration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Configuration retrieval failed: {str(e)}"
        )

@router.post("/reload-config")
async def reload_system_configuration() -> Dict[str, Any]:
    """
    Reload system configuration
    Useful for applying changes without restart
    """
    try:
        logger.info("Reloading system configuration...")
        
        from config.settings import reload_settings
        new_settings = reload_settings()
        
        if llm_provider_manager._initialized:
            llm_provider_manager._initialized = False
            await llm_provider_manager.initialize()
        
        if rag_workflow.graph:
            await rag_workflow.initialize()
        
        logger.info("Configuration reloaded successfully")
        
        return {
            "message": "Configuration reloaded successfully",
            "timestamp": datetime.now().isoformat(),
            "enabled_providers": new_settings.get_enabled_providers(),
            "enabled_agents": new_settings.get_enabled_agents(),
            "enabled_tools": new_settings.get_enabled_tools()
        }
        
    except Exception as e:
        logger.error(f"Configuration reload failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Configuration reload failed: {str(e)}"
        )

async def _log_query_completion(
    query: str,
    user_id: Optional[str],
    workflow_id: str,
    processing_time: float
):
    """Background task to log query completion"""
    try:
        logger.info(
            "Query completed successfully",
            extra={
                "query_preview": query[:100],
                "user_id": user_id,
                "workflow_id": workflow_id,
                "processing_time": processing_time,
                "event_type": "query_completion"
            }
        )
    except Exception as e:
        logger.error(f"Failed to log query completion: {e}")