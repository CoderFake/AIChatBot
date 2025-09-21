
"""
Chat endpoint with SSE streaming for multi-agent workflow
Single route with middleware for user/org identification
"""
import json
from typing import AsyncGenerator, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_db
from api.v1.middleware.middleware import JWTAuth
from models.schemas.request.chat import ChatRequest
from services.chat.chat_service import ChatService
from common.types import UserRole
from utils.logging import get_logger
from utils.language_utils import detect_language, get_localized_message

logger = get_logger(__name__)
router = APIRouter()


@router.post("/create-session")
async def create_chat_session(
    request: Dict[str, Any] = None,
    user_context: Dict[str, Any] = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new chat session for user
    Optionally generate title from first message if provided
    """
    try:
        tenant_id = user_context.get("tenant_id")
        user_id = user_context.get("user_id")

        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        from services.chat.session_manager_service import SessionManagerService

        session_manager = SessionManagerService(db)

        title = None
        if request and "title" in request:
            title = request["title"]

        result = await session_manager.create_session(
            user_id=user_id,
            tenant_id=tenant_id,
            title=title
        )

        return result

    except Exception as e:
        logger.error(f"Failed to create chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def get_chat_sessions(
    skip: int = 0,
    limit: int = 20,
    user_context: Dict[str, Any] = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get user's chat sessions
    """
    try:
        tenant_id = user_context.get("tenant_id")
        user_id = user_context.get("user_id")

        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        chat_service = ChatService(db)
        return await chat_service.get_chat_sessions(
            user_id=user_id,
            tenant_id=tenant_id,
            skip=skip,
            limit=limit
        )

    except Exception as e:
        logger.error(f"Failed to get chat sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    skip: int = 0,
    limit: int = 50,
    user_context: Dict[str, Any] = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get messages for a specific chat session
    """
    try:
        tenant_id = user_context.get("tenant_id")
        user_id = user_context.get("user_id")

        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        chat_service = ChatService(db)
        return await chat_service.get_session_messages(
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            skip=skip,
            limit=limit
        )
    except Exception as e:
        logger.error(f"Failed to get session messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    user_context: Dict[str, Any] = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a chat session and all its messages
    """
    try:
        tenant_id = user_context.get("tenant_id")
        user_id = user_context.get("user_id")

        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        chat_service = ChatService(db)
        result = await chat_service.delete_session(
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id
        )

        return {"success": result, "message": "Session deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/sessions/{session_id}/title")
async def update_session_title(
    session_id: str,
    request: Dict[str, str],
    user_context: Dict[str, Any] = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update the title of a chat session
    """
    try:
        tenant_id = user_context.get("tenant_id")
        user_id = user_context.get("user_id")
        new_title = request.get("title")

        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")
        if not new_title or not new_title.strip():
            raise HTTPException(status_code=400, detail="Title is required")

        chat_service = ChatService(db)
        result = await chat_service.update_session_title(
            session_id=session_id,
            new_title=new_title.strip(),
            user_id=user_id,
            tenant_id=tenant_id
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update session title: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def chat(
    request: ChatRequest,
    user_context: Dict[str, Any] = Depends(JWTAuth.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Multi-agent chat workflow with orchestrator, semantic routing, and parallel execution
    Returns streaming response with progress updates
    """
    try:
        query = request.query
        session_id_str = request.session_id

        tenant_id = user_context.get("tenant_id")
        department_id = user_context.get("department_id")
        user_id = user_context.get("user_id")
        access_level = request.access_scope.visibility or "public"

        if user_context.get("role") == UserRole.USER.value:
            access_level = "public"

        if not tenant_id:
            raise HTTPException(status_code=400, detail="Tenant ID required")

        detected_language = detect_language(query)
        logger.info(f"Starting multi-agent workflow for tenant {tenant_id}: {query[:50]}...")

        chat_service = ChatService(db)
        
        user_context = await chat_service.enrich_user_context(user_context, tenant_id)
        
        chat_session = await chat_service.get_or_create_session(
            session_id_str=session_id_str,
            user_id=user_id,
            tenant_id=tenant_id
        )
        session_id = chat_session.id
        
        session_title = None
        logger.info(f"Session {chat_session.id} message_count: {chat_session.message_count}")

        if chat_session.message_count == 0 and query.strip():
            logger.info(f"First message - generating title for session {chat_session.id}")
            from services.chat.title_service import TitleService
            title_service = TitleService(db)

            session_title = await title_service.generate_and_update_session_title(
                session=chat_session,
                first_message=query,
                tenant_id=tenant_id,
                user_id=user_id
            )
            logger.info(f"Generated session title: {session_title}")
        else:
            logger.info(f"Existing session - skipping title generation, message_count: {chat_session.message_count}")

        is_first_message = chat_session.message_count == 0

        async def event_generator() -> AsyncGenerator[str, None]:
            try:
                if session_title:
                    yield f"data: {json.dumps({'type': 'title', 'title': session_title})}\n\n"

                async for event in chat_service.execute_multi_agent_workflow(
                    query=query,
                    access_level=access_level,
                    session_id=session_id,
                    tenant_id=tenant_id,
                    department_id=department_id,
                    user_context=user_context,
                    detected_language=detected_language,
                    user_message_id=None,  # Will be created in workflow for first message
                    session_title=session_title,
                    is_first_message=is_first_message
                ):
                    yield event

            except Exception as e:
                logger.error(f"SSE stream error: {e}")
                error_event = {
                    'sse_type': 4,
                    'type': 'end',
                    'message': get_localized_message('processing_error', detected_language),
                    'progress': 0,
                    'status': 'error',
                    'error': str(e)
                }
                yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Transfer-Encoding": "chunked",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*"
            }
        )

    except Exception as e:
        logger.error(f"Chat query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def chat_health():
    """Health check for chat service"""
    try:
        from workflows.langgraph.workflow_graph import multi_agent_rag_workflow
        
        workflow_healthy = await multi_agent_rag_workflow.health_check()
        
        return {
            "status": "healthy" if workflow_healthy else "unhealthy",
            "workflow_initialized": workflow_healthy,
            "service": "chat"
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "service": "chat"
        }

