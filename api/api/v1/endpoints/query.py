from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Any, List, Optional
import asyncio
from datetime import datetime
from pydantic import BaseModel, Field

from config.settings import get_settings
from core.exceptions import WorkflowError, LLMProviderError
from workflows.langgraph.workflow_graph import rag_workflow
from services.llm.provider_manager import llm_provider_manager
from services.tools.tool_manager import tool_manager
from utils.logging import get_logger, log_performance

router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()

# Request Models
class QueryRequest(BaseModel):
    """Request model cho RAG query"""
    query: str = Field(..., description="Câu hỏi của user", max_length=1000)
    user_id: Optional[str] = Field(None, description="ID của user (optional)")
    session_id: Optional[str] = Field(None, description="Session ID cho conversation tracking")
    conversation_history: Optional[List[Dict[str, Any]]] = Field(
        default=[], 
        description="Lịch sử hội thoại trước đó"
    )
    provider: Optional[str] = Field(None, description="Chỉ định provider cụ thể (optional)")
    model: Optional[str] = Field(None, description="Chỉ định model cụ thể (optional)")
    top_k: Optional[int] = Field(5, description="Số lượng documents trả về", ge=1, le=20)
    threshold: Optional[float] = Field(0.2, description="Threshold cho similarity search", ge=0.0, le=1.0)

class TestToolRequest(BaseModel):
    """Request model cho testing individual tools"""
    tool_name: str = Field(..., description="Tên tool cần test")
    query: str = Field(..., description="Query để test tool")

# Response Models
class QueryResponse(BaseModel):
    """Response model cho RAG query"""
    response: str = Field(..., description="Câu trả lời được generate")
    sources: List[Dict[str, Any]] = Field(default=[], description="Nguồn tài liệu tham khảo")
    follow_up_questions: List[str] = Field(default=[], description="Câu hỏi tiếp theo gợi ý")
    workflow_id: str = Field(..., description="ID của workflow execution")
    processing_time: float = Field(..., description="Thời gian xử lý (seconds)")
    tokens_used: int = Field(default=0, description="Số tokens đã sử dụng")
    error: Optional[str] = Field(None, description="Lỗi nếu có")

@router.post("/rag", response_model=QueryResponse)
@log_performance()
async def rag_query(request: QueryRequest, background_tasks: BackgroundTasks):
    """
    Main RAG query endpoint sử dụng LangGraph workflow
    """
    try:
        logger.info(f"Processing RAG query: {request.query[:100]}...")
        
        # Validate workflow is initialized
        if not rag_workflow.initialized:
            logger.info("Initializing RAG workflow...")
            await rag_workflow.initialize()
        
        # Process query through LangGraph workflow
        result = await rag_workflow.process_query(
            query=request.query,
            user_id=request.user_id,
            session_id=request.session_id,
            conversation_history=request.conversation_history
        )
        
        # Log successful query
        background_tasks.add_task(
            _log_query_success,
            request.query,
            request.user_id,
            result["workflow_id"],
            result["processing_time"]
        )
        
        return QueryResponse(
            response=result["response"],
            sources=result["sources"],
            follow_up_questions=result["follow_up_questions"],
            workflow_id=result["workflow_id"],
            processing_time=result["processing_time"],
            tokens_used=result["tokens_used"],
            error=result["error"]
        )
        
    except WorkflowError as e:
        logger.error(f"Workflow error: {e}")
        raise HTTPException(status_code=500, detail=f"Workflow error: {str(e)}")
    
    except LLMProviderError as e:
        logger.error(f"LLM provider error: {e}")
        raise HTTPException(status_code=502, detail=f"LLM provider error: {str(e)}")
    
    except Exception as e:
        logger.error(f"Unexpected error in RAG query: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/test-tool")
async def test_tool(request: TestToolRequest):
    """
    Test individual tool functionality
    """
    try:
        logger.info(f"Testing tool {request.tool_name} với query: {request.query}")
        
        # Initialize tool manager if needed
        if not tool_manager.initialized:
            await tool_manager.initialize()
        
        # Check if tool should be used
        should_use = await tool_manager.should_use_tool(request.tool_name, request.query)
        
        if not should_use:
            return {
                "tool": request.tool_name,
                "query": request.query,
                "should_use": False,
                "message": f"Tool {request.tool_name} không phù hợp cho query này"
            }
        
        # Execute tool
        result = await tool_manager.execute_tool(request.tool_name, request.query)
        
        return {
            "tool": request.tool_name,
            "query": request.query,
            "should_use": True,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Tool test failed: {e}")
        raise HTTPException(status_code=500, detail=f"Tool test failed: {str(e)}")

@router.get("/tools/status")
async def get_tools_status():
    """
    Get status của tất cả tools
    """
    try:
        if not tool_manager.initialized:
            await tool_manager.initialize()
        
        tools_info = tool_manager.get_tool_info()
        usage_stats = tool_manager.get_usage_statistics()
        
        return {
            "tools": tools_info,
            "usage_stats": usage_stats,
            "enabled_tools": settings.enabled_tools,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get tools status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get tools status")

@router.get("/providers/status")
async def get_providers_status():
    """
    Get status của tất cả LLM providers
    """
    try:
        if not llm_provider_manager.initialized:
            await llm_provider_manager.initialize()
        
        health_status = await llm_provider_manager.health_check_all()
        usage_stats = await llm_provider_manager.get_usage_statistics()
        available_models = llm_provider_manager.get_available_models()
        
        return {
            "providers": {
                "health": health_status,
                "usage_stats": usage_stats,
                "available_models": available_models
            },
            "enabled_providers": settings.enabled_providers,
            "default_provider": settings.DEFAULT_LLM_PROVIDER,
            "configuration": {
                provider: settings.get_provider_config(provider)
                for provider in settings.enabled_providers
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get providers status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get providers status")

@router.post("/test-llm")
async def test_llm_provider(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    test_prompt: str = "Hello, how are you?"
):
    """
    Test specific LLM provider
    """
    try:
        if not llm_provider_manager.initialized:
            await llm_provider_manager.initialize()
        
        # Get LLM instance
        llm = await llm_provider_manager.get_llm(provider=provider, model=model)
        
        # Test invoke
        start_time = asyncio.get_event_loop().time()
        response = await llm.ainvoke(test_prompt)
        execution_time = asyncio.get_event_loop().time() - start_time
        
        return {
            "provider": llm.provider.provider_name,
            "model": model or "default",
            "test_prompt": test_prompt,
            "response": response.content if hasattr(response, 'content') else str(response),
            "execution_time": execution_time,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"LLM provider test failed: {e}")
        return {
            "provider": provider or "auto-selected",
            "model": model or "default",
            "test_prompt": test_prompt,
            "response": None,
            "execution_time": 0,
            "success": False,
            "error": str(e)
        }

@router.get("/workflow/status")
async def get_workflow_status():
    """
    Get status của LangGraph workflow
    """
    try:
        workflow_health = await rag_workflow.health_check()
        
        return {
            "workflow": {
                "initialized": rag_workflow.initialized,
                "healthy": workflow_health,
                "config": {
                    "max_iterations": rag_workflow.config.max_iterations,
                    "timeout_seconds": rag_workflow.config.timeout_seconds,
                    "enable_reflection": rag_workflow.config.enable_reflection,
                    "enable_semantic_routing": rag_workflow.config.enable_semantic_routing,
                    "enable_document_grading": rag_workflow.config.enable_document_grading,
                    "enable_citation_generation": rag_workflow.config.enable_citation_generation,
                    "enable_query_expansion": rag_workflow.config.enable_query_expansion,
                    "enable_hallucination_check": rag_workflow.config.enable_hallucination_check,
                }
            },
            "langgraph_config": settings.get_langgraph_config(),
            "enabled_workflows": settings.enabled_workflows,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get workflow status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get workflow status")

@router.post("/reload-config")
async def reload_configuration():
    """
    Reload configuration từ admin settings
    """
    try:
        logger.info("Reloading system configuration...")
        
        # Reload tool configuration
        if tool_manager.initialized:
            await tool_manager.reload_configuration()
        
        # Reload LLM provider configuration
        # (This would require implementing reload in provider manager)
        
        # Reload workflow configuration
        if rag_workflow.initialized:
            await rag_workflow._load_admin_configuration()
        
        logger.info("Configuration reloaded successfully")
        
        return {
            "message": "Configuration reloaded successfully",
            "timestamp": datetime.now().isoformat(),
            "enabled_tools": settings.enabled_tools,
            "enabled_providers": settings.enabled_providers,
            "enabled_workflows": settings.enabled_workflows
        }
        
    except Exception as e:
        logger.error(f"Failed to reload configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to reload configuration")

@router.get("/admin/overview")
async def get_admin_overview():
    """
    Get comprehensive overview cho admin dashboard
    """
    try:
        # Get tools status
        tools_stats = tool_manager.get_usage_statistics() if tool_manager.initialized else {}
        
        # Get providers status
        providers_health = await llm_provider_manager.health_check_all() if llm_provider_manager.initialized else {}
        
        # Get workflow status
        workflow_health = await rag_workflow.health_check() if rag_workflow.initialized else False
        
        return {
            "system": {
                "app_name": settings.APP_NAME,
                "environment": settings.ENV,
                "version": "2.0.0",
                "framework": "FastAPI + LangGraph"
            },
            "components": {
                "tools": {
                    "total": tools_stats.get("total_tools", 0),
                    "enabled": tools_stats.get("enabled_tools", 0),
                    "stats": tools_stats.get("tool_stats", {})
                },
                "providers": {
                    "enabled": settings.enabled_providers,
                    "health": providers_health,
                    "default": settings.DEFAULT_LLM_PROVIDER
                },
                "workflows": {
                    "healthy": workflow_health,
                    "enabled": settings.enabled_workflows
                }
            },
            "configuration": {
                "multi_tenant": settings.ENABLE_MULTI_TENANT,
                "admin_interface": settings.ENABLE_ADMIN_INTERFACE,
                "langgraph_debug": settings.ENABLE_LANGGRAPH_DEBUG,
                "cache_ttl": settings.CACHE_TTL
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get admin overview: {e}")
        raise HTTPException(status_code=500, detail="Failed to get admin overview")

# Background task functions
async def _log_query_success(query: str, user_id: Optional[str], workflow_id: str, processing_time: float):
    """Log successful query execution"""
    try:
        logger.info(
            f"Query completed successfully",
            extra={
                "query_preview": query[:100],
                "user_id": user_id,
                "workflow_id": workflow_id,
                "processing_time": processing_time
            }
        )
    except Exception as e:
        logger.error(f"Failed to log query success: {e}")
