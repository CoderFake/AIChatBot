from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
import asyncio
import uuid
from datetime import datetime

from api.schemas.chat_schemas import (
    ChatRequest, ChatResponse, ChatSession, StreamingChatRequest
)
from services.orchestrator.orchestrator_service import OrchestratorService
from services.llm.provider_manager import llm_provider_manager
from config.settings import get_settings
from utils.logging import get_logger

router = APIRouter(prefix="/chat", tags=["chat"])
logger = get_logger(__name__)
settings = get_settings()

orchestrator_service = OrchestratorService()

@router.post("/", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    background_tasks: BackgroundTasks
) -> ChatResponse:
    """
    🎯 Main Chat Endpoint với Intelligent Orchestrator
    
    Thay thế keyword-based routing bằng LLM orchestrator
    """
    
    session_id = request.session_id or str(uuid.uuid4())
    start_time = datetime.now()
    
    logger.info(f"💬 Chat request received - Session: {session_id}")
    logger.info(f"🔍 Query: {request.query[:100]}...")
    
    try:
        # Prepare user context for orchestrator
        user_context = {
            "conversation_history": request.conversation_history or [],
            "preferences": request.user_preferences or {},
            "session_info": {
                "session_id": session_id,
                "language": request.language,
                "start_time": start_time.isoformat()
            }
        }
        
        if getattr(settings, 'ENABLE_INTELLIGENT_ORCHESTRATOR', True):
            logger.info("Using Intelligent Orchestrator for agent selection")
            
            orchestrated_response = await orchestrator_service.orchestrate_query(
                query=request.query,
                language=request.language,
                user_context=user_context,
                session_id=session_id
            )
            
            response_content = orchestrated_response["response"]
            citations = orchestrated_response.get("citations", [])
            metadata = orchestrated_response.get("metadata", {})
            
            orchestration_method = metadata.get("orchestration_method", "unknown")
            selected_agents = metadata.get("selected_agents", [])
            
            logger.info(f"Orchestration completed using: {orchestration_method}")
            logger.info(f"Selected agents: {selected_agents}")
            
        else:
            logger.info("Orchestrator disabled, using simple LLM response")
            
            response_content, citations, metadata = await _get_simple_llm_response(
                request.query, request.language, user_context
            )
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        chat_response = ChatResponse(
            response=response_content,
            session_id=session_id,
            citations=citations,
            language=request.language,
            metadata={
                "execution_time": execution_time,
                "timestamp": datetime.now().isoformat(),
                "query_length": len(request.query),
                **metadata
            }
        )
        
        if getattr(settings, 'ENABLE_CONVERSATION_HISTORY', True):
            background_tasks.add_task(
                _save_conversation_history,
                session_id=session_id,
                user_query=request.query,
                bot_response=response_content,
                metadata=chat_response.metadata
            )
        
        logger.info(f"Chat response completed in {execution_time:.2f}s")
        return chat_response
        
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        
        error_response = await _get_error_response(
            request.query, request.language, str(e), session_id
        )
        
        return error_response

async def _get_simple_llm_response(
    query: str, 
    language: str, 
    user_context: Dict[str, Any]
) -> tuple[str, List[str], Dict[str, Any]]:
    """
    Simple LLM response without orchestration
    Fallback when orchestrator is disabled
    """
    
    try:
        enabled_providers = getattr(settings, 'enabled_providers', [])
        if not enabled_providers:
            raise ValueError("No LLM providers enabled in admin settings")
            
        llm = await llm_provider_manager.get_provider(enabled_providers[0])
        
        language_prompts = {
            "vi": f"""
Bạn là AI Assistant thông minh và hữu ích. Hãy trả lời câu hỏi sau một cách chính xác và chi tiết:

Câu hỏi: {query}

Hãy cung cấp thông tin hữu ích và thực tế. Nếu không chắc chắn về thông tin, hãy nói rõ điều đó.
""",
            "en": f"""
You are an intelligent and helpful AI Assistant. Please answer the following question accurately and in detail:

Question: {query}

Provide helpful and factual information. If uncertain about information, please clearly state that.
""",
            "ja": f"""
あなたは知的で役立つAIアシスタントです。以下の質問に正確かつ詳細に答えてください：

質問: {query}

役立つ事実に基づく情報を提供してください。情報が不確実な場合は、それを明確に述べてください。
""",
            "ko": f"""
당신은 지능적이고 도움이 되는 AI 어시스턴트입니다. 다음 질문에 정확하고 자세히 답변해 주세요:

질문: {query}

도움이 되고 사실적인 정보를 제공해 주세요. 정보가 불확실한 경우 명확히 말씀해 주세요.
"""
        }
        
        prompt = language_prompts.get(language, language_prompts["vi"])
        
        response = await llm.ainvoke(prompt)
        
        return (
            response.content,
            ["General AI Knowledge"],  # Simple citation
            {
                "method": "simple_llm",
                "provider": enabled_providers[0],
                "confidence": 0.75
            }
        )
        
    except Exception as e:
        logger.error(f"Simple LLM response failed: {e}")
        
        fallback_messages = {
            "vi": "Xin lỗi, tôi không thể xử lý câu hỏi của bạn lúc này. Vui lòng thử lại sau.",
            "en": "Sorry, I cannot process your question at this time. Please try again later.",
            "ja": "申し訳ありませんが、現在ご質問を処理できません。後でもう一度お試しください。",
            "ko": "죄송합니다. 현재 질문을 처리할 수 없습니다. 나중에 다시 시도해 주세요."
        }
        
        return (
            fallback_messages.get(language, fallback_messages["vi"]),
            [],
            {"method": "fallback", "error": str(e), "confidence": 0.1}
        )

async def _get_error_response(
    query: str,
    language: str, 
    error_message: str,
    session_id: str
) -> ChatResponse:
    """Generate error response for failed chat requests"""
    
    error_messages = {
        "vi": f"Xin lỗi, đã xảy ra lỗi khi xử lý câu hỏi của bạn: {error_message}",
        "en": f"Sorry, an error occurred while processing your question: {error_message}",
        "ja": f"申し訳ありませんが、ご質問の処理中にエラーが発生しました: {error_message}",
        "ko": f"죄송합니다. 질문 처리 중 오류가 발생했습니다: {error_message}"
    }
    
    return ChatResponse(
        response=error_messages.get(language, error_messages["vi"]),
        session_id=session_id,
        citations=[],
        language=language,
        metadata={
            "error": True,
            "error_message": error_message,
            "timestamp": datetime.now().isoformat(),
            "confidence": 0.0
        }
    )

async def _save_conversation_history(
    session_id: str,
    user_query: str,
    bot_response: str,
    metadata: Dict[str, Any]
) -> None:
    """
    Background task to save conversation history
    Implement database storage logic here
    """
    
    try:
        
        conversation_record = {
            "session_id": session_id,
            "user_query": user_query,
            "bot_response": bot_response,
            "metadata": metadata,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Saving conversation history for session: {session_id}")
        
    except Exception as e:
        logger.error(f"Failed to save conversation history: {e}")

@router.get("/health")
async def chat_health_check():
    """Health check for chat service"""
    
    try:
        orchestrator_status = "enabled" if getattr(settings, 'ENABLE_INTELLIGENT_ORCHESTRATOR', True) else "disabled"
        available_agents = list(orchestrator_service.agents.keys())
        enabled_providers = getattr(settings, 'enabled_providers', [])
        
        return {
            "status": "healthy",
            "orchestrator": orchestrator_status,
            "available_agents": available_agents,
            "enabled_providers": enabled_providers,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@router.post("/stream", response_model=Dict[str, Any])
async def streaming_chat_endpoint(request: StreamingChatRequest):
    """
    Streaming Chat Endpoint với Orchestrator Support
    """

    
    logger.info("Streaming chat requested, using regular orchestrated chat")
    
    chat_request = ChatRequest(
        query=request.query,
        language=request.language,
        session_id=request.session_id,
        conversation_history=request.conversation_history,
        user_preferences=request.user_preferences
    )
    
    response = await chat_endpoint(chat_request, BackgroundTasks())
    
    return {
        "response": response.response,
        "session_id": response.session_id,
        "citations": response.citations,
        "metadata": {
            **response.metadata,
            "streaming": False,
            "note": "Streaming support for orchestrator coming soon"
        }
    } 