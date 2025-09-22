"""
Chat service layer for managing chat sessions and messages
"""
import uuid
import inspect
from typing import List, Dict, Any, Optional, AsyncGenerator     
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from fastapi import HTTPException

from models.database.chat import ChatSession, ChatMessage
from services.orchestrator.orchestrator import Orchestrator
from utils.logging import get_logger
from utils.datetime_utils import DateTimeManager
import asyncio
import json

logger = get_logger(__name__)


class ChatService:
    """
    Chat service for managing chat sessions and messages
    - Create and manage chat sessions
    - Save and retrieve chat messages
    - Handle session lifecycle
    """

    def __init__(self, db: AsyncSession = None):
        self.db = db
        self.orchestrator = Orchestrator(db)
        self._cache_initialized = False

    async def _ensure_cache_initialized(self):
        """Ensure cache manager is initialized - only initialize if not already done globally"""
        if not self._cache_initialized:
            try:
                cache_mgr = self.orchestrator.cache_manager()
                if not cache_mgr._initialized:
                    logger.warning("Cache manager not initialized globally, initializing locally")
                    await cache_mgr.initialize()
                self._cache_initialized = True
            except Exception as e:
                logger.warning(f"Cache initialization failed: {e}")
                self._cache_initialized = True

    async def _invalidate_chat_sessions_cache(self, tenant_id: str, user_id: Optional[str]):
        """Invalidate chat sessions cache for a specific user"""
        try:
            await self._ensure_cache_initialized()
            pattern = f"chat_sessions_{tenant_id}_{user_id or 'anonymous'}_*"
            cache_mgr = self.orchestrator.cache_manager()
            deleted_count = await cache_mgr.delete_pattern(pattern)
            if deleted_count > 0:
                logger.info(f"Invalidated {deleted_count} chat session cache keys for user {user_id or 'anonymous'}")
        except Exception as e:
            logger.error(f"Failed to invalidate chat sessions cache: {e}")

    async def _invalidate_chat_messages_cache(self, session_id: str):
        """Invalidate chat messages cache for a specific session"""
        try:
            await self._ensure_cache_initialized()
            pattern = f"chat_messages_{session_id}_*"
            cache_mgr = self.orchestrator.cache_manager()
            deleted_count = await cache_mgr.delete_pattern(pattern)
            if deleted_count > 0:
                logger.info(f"Invalidated {deleted_count} chat message cache keys for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate chat messages cache: {e}")

    async def create_chat_session(
        self,
        user_id: Optional[str],
        tenant_id: str,
        title: Optional[str] = None
    ) -> ChatSession:
        """
        Create a new chat session
        """
        try:
            chat_session = ChatSession(
                user_id=user_id,
                tenant_id=tenant_id,
                is_anonymous=user_id is None,
                title=title,
                message_count=0
            )

            self.db.add(chat_session)
            await self.db.commit()
            await self.db.refresh(chat_session)

            await self._invalidate_chat_sessions_cache(tenant_id, user_id)

            logger.info(f"Created new chat session: {chat_session.id} for user {user_id or 'anonymous'}")
            return chat_session

        except Exception as e:
            logger.error(f"Failed to create chat session: {e}")
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to create chat session: {str(e)}")

    async def get_or_create_session(
        self,
        session_id_str: Optional[str],
        user_id: Optional[str],
        tenant_id: str
    ) -> ChatSession:
        """
        Get existing session or create new one if not exists
        """
        session_id = None
        if session_id_str:
            try:
                session_id = uuid.UUID(session_id_str)
            except ValueError:
                session_id = uuid.uuid4()
        else:
            session_id = uuid.uuid4()

        stmt = select(ChatSession).where(ChatSession.id == session_id)
        result = await self.db.execute(stmt)
        chat_session = result.scalar_one_or_none()

        if not chat_session:
            chat_session = await self.create_chat_session(
                user_id=user_id,
                tenant_id=tenant_id,
                title=None
            )
        else:
            chat_session.update_activity()
            await self.db.commit()
            logger.info(f"Using existing chat session: {chat_session.id}")

        return chat_session

    async def save_message(
        self,
        session_id: uuid.UUID,
        query: str,
        language: Optional[str] = None,
        processing_time: Optional[float] = None,
        model_used: Optional[str] = None,
        confidence_score: Optional[float] = None,
        chat_metadata: Optional[Dict[str, Any]] = None,
        response: Optional[str] = None
    ) -> ChatMessage:
        """
        Save a chat message to database with cache-first approach
        """
        try:
            message_data = {
                "session_id": session_id,
                "query": query,
                "language": language,
                "processing_time": processing_time,
                "model_used": model_used,
                "confidence_score": confidence_score,
                "chat_metadata": chat_metadata,
                "response": response
            }

            message = ChatMessage(**message_data)

            self.db.add(message)
            await self.db.commit()
            await self.db.refresh(message)

            updated_message_data = {
                "session_id": message.session_id,
                "query": message.query,
                "response": message.response,
                "language": message.language,
                "processing_time": message.processing_time,
                "model_used": message.model_used,
                "confidence_score": message.confidence_score,
                "chat_metadata": message.chat_metadata,
                "created_at": message.created_at.isoformat() if message.created_at else None
            }
            await self._cache_message(updated_message_data)

            await self.update_session_message_count(session_id)

            await self._invalidate_chat_messages_cache(str(session_id))
            await self.invalidate_message_cache(session_id)

            logger.info(f"Saved message for session {session_id}")
            return message

        except Exception as e:
            logger.error(f"Failed to save message: {e}")
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to save message: {str(e)}")


    async def get_chat_sessions(
        self,
        user_id: Optional[str],
        tenant_id: str,
        skip: int = 0,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Get user's chat sessions with caching (1 hour TTL)
        """
        try:
            await self._ensure_cache_initialized()

            cache_key = f"chat_sessions_{tenant_id}_{user_id or 'anonymous'}_{skip}_{limit}"
            cache_mgr = self.orchestrator.cache_manager()
            cached_sessions = await cache_mgr.get(cache_key)
            if cached_sessions:
                logger.info(f"Retrieved chat sessions from cache for user {user_id or 'anonymous'} in tenant {tenant_id}")
                return cached_sessions

            stmt = select(ChatSession).where(
                ChatSession.tenant_id == tenant_id,
                ChatSession.user_id == user_id
            ).order_by(desc(ChatSession.last_activity)).offset(skip).limit(limit)

            result = await self.db.execute(stmt)
            sessions = result.scalars().all()

            session_list = []
            for session in sessions:
                if session.title:
                    display_title = session.title
                elif session.message_count > 0:
                    display_title = f"Chat {str(session.id)[:8]}"
                else:
                    display_title = None
                
                session_list.append({
                    "session_id": str(session.id),
                    "title": display_title,
                    "message_count": session.message_count,
                    "last_activity": session.last_activity.isoformat(),
                    "created_at": session.created_at.isoformat(),
                    "is_anonymous": session.is_anonymous
                })

            sessions_data = {
                "sessions": session_list,
                "total": len(session_list),
                "skip": skip,
                "limit": limit
            }

            await cache_mgr.set(cache_key, sessions_data, ttl=3600)
            logger.info(f"Cached chat sessions for user {user_id or 'anonymous'} in tenant {tenant_id}")

            return sessions_data

        except Exception as e:
            logger.error(f"Failed to get chat sessions: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get chat sessions: {str(e)}")

    async def get_session_messages(
        self,
        session_id: str,
        user_id: Optional[str],
        tenant_id: str,
        skip: int = 0,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get messages for a specific chat session with caching (1 hour TTL)
        """
        try:
            await self._ensure_cache_initialized()

            cache_key = f"chat_messages_{session_id}_{skip}_{limit}"
            cache_mgr = self.orchestrator.cache_manager()
            cached_messages = await cache_mgr.get(cache_key)
            if cached_messages:
                logger.info(f"Retrieved chat messages from cache for session {session_id}")
                return cached_messages
            try:
                session_uuid = uuid.UUID(session_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid session ID format")

            stmt = select(ChatSession).where(
                ChatSession.id == session_uuid,
                ChatSession.tenant_id == tenant_id,
                ChatSession.user_id == user_id
            )
            result = await self.db.execute(stmt)
            session = result.scalar_one_or_none()

            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            stmt = select(ChatMessage).where(
                ChatMessage.session_id == session_uuid
            ).order_by(ChatMessage.created_at).offset(skip).limit(limit)

            result = await self.db.execute(stmt)
            messages = result.scalars().all()

            message_list = []
            for message in messages:
                role = "assistant" if message.response else "user"
                content = message.response if message.response else message.query

                message_list.append({
                    "id": str(message.id),
                    "content": content,
                    "role": role,
                    "query": message.query,
                    "response": message.response,
                    "created_at": message.created_at.isoformat(),
                    "language": message.language,
                    "processing_time": message.processing_time,
                    "model_used": message.model_used,
                    "confidence_score": message.confidence_score,
                    "chat_metadata": message.chat_metadata
                })

            messages_data = {
                "session_id": session_id,
                "messages": message_list,
                "total": len(message_list),
                "skip": skip,
                "limit": limit
            }

            await cache_mgr.set(cache_key, messages_data, ttl=3600)
            logger.info(f"Cached chat messages for session {session_id}")

            return messages_data

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get session messages: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get session messages: {str(e)}")

    async def get_recent_messages(self, session_id: uuid.UUID, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get recent messages from cache or database (prioritize cache)
        Returns the last 'limit' user-assistant conversation pairs
        """
        try:
            await self._ensure_cache_initialized()

            cache_key = f"chat_recent_messages_{session_id}"
            cache_mgr = self.orchestrator.cache_manager()
            cached_messages = await cache_mgr.get(cache_key)
            if cached_messages:
                logger.info(f"Retrieved {len(cached_messages)} recent messages from cache for session {session_id}")
                return cached_messages

            db_limit = limit * 2

            stmt = select(ChatMessage).where(
                ChatMessage.session_id == session_id
            ).order_by(desc(ChatMessage.created_at)).limit(db_limit)

            result = await self.db.execute(stmt)
            messages = result.scalars().all()

            message_list = []
            for message in reversed(messages):
                message_list.append({
                    "query": message.query,
                    "response": message.response,
                    "created_at": message.created_at.isoformat(),
                    "has_response": message.is_ai_response
                })

            conversation_pairs = []
            i = 0
            while i < len(message_list) and len(conversation_pairs) < limit:
                if not message_list[i]["has_response"]:
                    user_msg = message_list[i]
                    assistant_msg = None

                    for j in range(i + 1, len(message_list)):
                        if message_list[j]["has_response"]:
                            assistant_msg = message_list[j]
                            break

                    if assistant_msg:
                        conversation_pairs.append({
                            "user": user_msg,
                            "assistant": assistant_msg
                        })

                i += 1

            if not conversation_pairs:
                recent_messages = message_list[-limit:] if len(message_list) > limit else message_list
            else:
                recent_messages = []
                for pair in conversation_pairs[-limit:]:
                    recent_messages.extend([pair["user"], pair["assistant"]])

            await cache_mgr.set(cache_key, recent_messages, ttl=3600)
            logger.info(f"Cached {len(recent_messages)} recent messages for session {session_id}")

            return recent_messages

        except Exception as e:
            logger.error(f"Failed to get recent messages: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get recent messages: {str(e)}")

    async def invalidate_message_cache(self, session_id: uuid.UUID) -> None:
        """
        Invalidate cache for a session's messages
        """
        try:
            await self._ensure_cache_initialized()
            cache_key = f"chat_recent_messages_{session_id}"
            cache_mgr = self.orchestrator.cache_manager()
            await cache_mgr.delete(cache_key)
            logger.info(f"Invalidated message cache for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate message cache: {e}")

    async def update_session_message_count(self, session_id: uuid.UUID) -> None:
        """
        Update message count for a session
        """
        try:
            stmt = select(ChatSession).where(ChatSession.id == session_id)
            result = await self.db.execute(stmt)
            session = result.scalar_one_or_none()

            if session:
                stmt = select(ChatMessage).where(ChatMessage.session_id == session_id)
                result = await self.db.execute(stmt)
                messages = result.scalars().all()
                session.message_count = len(messages)
                await self.db.commit()

                logger.info(f"Updated message count for session {session_id}: {session.message_count}")

        except Exception as e:
            logger.error(f"Failed to update session message count: {e}")
            await self.db.rollback()

    async def delete_session(self, session_id: str, user_id: Optional[str], tenant_id: str) -> bool:
        """
        Delete a chat session and all its messages, with cache invalidation
        """
        try:
            session_uuid = uuid.UUID(session_id)

            stmt = select(ChatSession).where(
                ChatSession.id == session_uuid,
                ChatSession.tenant_id == tenant_id,
                ChatSession.user_id == user_id
            )
            result = await self.db.execute(stmt)
            session = result.scalar_one_or_none()

            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            delete_messages_stmt = select(ChatMessage).where(ChatMessage.session_id == session_uuid)
            result = await self.db.execute(delete_messages_stmt)
            messages = result.scalars().all()

            for message in messages:
                await self.db.delete(message)

            await self.db.delete(session)

            await self._invalidate_chat_sessions_cache(tenant_id, user_id)
            await self._invalidate_chat_messages_cache(session_id)

            await self.db.commit()

            logger.info(f"Deleted chat session: {session_id} with {len(messages)} messages")
            return True

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")

    async def update_session_title(self, session_id: str, new_title: str, user_id: Optional[str], tenant_id: str) -> Dict[str, Any]:
        """
        Update the title of a chat session
        """
        try:
            session_uuid = uuid.UUID(session_id)

            stmt = select(ChatSession).where(
                ChatSession.id == session_uuid,
                ChatSession.tenant_id == tenant_id,
                ChatSession.user_id == user_id
            )
            result = await self.db.execute(stmt)
            session = result.scalar_one_or_none()

            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            session.title = new_title
            await self.db.commit()

            await self._invalidate_chat_sessions_cache(tenant_id, user_id)

            logger.info(f"Updated title for session {session_id}: {new_title}")
            return {
                "session_id": session_id,
                "title": new_title,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to update session title: {e}")
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to update session title: {str(e)}")

    async def _cache_message(self, message_data: Dict[str, Any]) -> None:
        """
        Cache message data immediately before DB save
        """
        try:
            await self._ensure_cache_initialized()
            session_id = str(message_data["session_id"])
            cache_key = f"chat_message_{session_id}_{message_data.get('created_at', 'temp')}"

            cache_mgr = self.orchestrator.cache_manager()
            await cache_mgr.set(cache_key, message_data, ttl=3600) 
            logger.debug(f"Cached message for session {session_id}")
        except Exception as e:
            logger.warning(f"Failed to cache message: {e}")

    async def enrich_user_context(self, user_context: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
        """
        Enrich user context with tenant information using cached timezone lookup
        """
        try:
            from utils.datetime_utils import DateTimeManager
            
            tenant_timezone = await DateTimeManager.get_tenant_timezone(tenant_id, self.db)
            tenant_now = await DateTimeManager.tenant_now_cached(tenant_id, self.db)

            user_context["timezone"] = tenant_timezone
            user_context["tenant_current_datetime"] = tenant_now.isoformat()
            logger.debug(f"Using tenant timezone: {tenant_timezone}")
            
            return user_context
            
        except Exception as e:
            logger.warning(f"Failed to enrich user context with tenant timezone: {e}")
            user_context["timezone"] = "UTC"
            user_context["tenant_current_datetime"] = DateTimeManager.system_now().isoformat()
            return user_context

    async def _get_conversation_history(self, session_id: uuid.UUID, user_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get conversation history for the session (cache-first approach)"""
        try:
            recent_messages = await self.get_recent_messages(session_id, limit=5)

            conversation_history = []
            for msg in recent_messages:
                if msg.get("query"):
                    conversation_history.append({
                        "content": msg["query"],
                        "type": "human",
                        "timestamp": msg.get("created_at", "")
                    })

                if msg.get("response"):
                    conversation_history.append({
                        "content": msg["response"],
                        "type": "assistant",
                        "timestamp": msg.get("created_at", "")
                    })

            logger.info(f"Retrieved {len(conversation_history)} messages from cache/database for session {session_id}")
            return conversation_history

        except Exception as e:
            logger.warning(f"Failed to get conversation history: {e}")
            return []

    async def execute_multi_agent_workflow(
        self,
        query: str,
        access_level: str,
        session_id: uuid.UUID,
        tenant_id: str,
        department_id: Optional[str],
        user_context: Dict[str, Any],
        detected_language: str,
        user_message_id: Optional[str],
        session_title: Optional[str] = None,
        is_first_message: bool = False
    ) -> AsyncGenerator[str, None]:
        """
        Execute multi-agent workflow using existing LangGraph implementation
        """
        try:
            from langchain_core.runnables import RunnableConfig
            from workflows.langgraph.workflow_graph import stream_rag_query

            config = RunnableConfig(
                configurable={
                    "thread_id": str(session_id),
                    "checkpoint_ns": f"chat_session_{tenant_id}",
                },
                metadata={
                    "user_id": user_context.get("user_id"),
                    "tenant_id": tenant_id,
                    "department_id": department_id,
                    "detected_language": detected_language,
                    "access_scope": access_level
                }
            )

            progress_messages = []
            pending_error_response: Optional[str] = None
            pending_error_details: Optional[str] = None
            pending_error_sources: List[Any] = []
            pending_error_followups: List[Any] = []
            pending_error_flow_actions: List[Any] = []
            pending_error_execution_metadata: Dict[str, Any] = {}
            pending_error_progress: int = 0
            workflow_status: str = "running"
            final_response_emitted = False

            messages = await self._get_conversation_history(session_id, user_context)

            logger.info(f"STARTING_WORKFLOW: session={session_id}, query='{query}'")
            start_data = {
                "message": "Starting workflow processing...",
                "progress": 0,
                "status": "started"
            }
            
            if session_title:
                start_data["session_title"] = session_title
                logger.info(f"Including session title in start event: {session_title}")
                
            yield self._create_sse_event(1, "start", start_data)

            async for chunk in stream_rag_query(
                query=query,
                user_context=user_context,
                messages=messages,
                config=config,
                bot_name="AI Assistant",
                organization_name="Organization",
                tenant_description="",
                access_level=access_level
            ):
                if chunk.get("type") != "node":
                    continue

                node_name = chunk.get("node", "")
                output = chunk.get("output") or {}

                if not output:
                    continue

                if output.get("should_yield"):
                    progress_msg = output.get("progress_message", "")
                    if progress_msg:
                        progress_messages.append({
                            "node": node_name,
                            "message": progress_msg,
                            "timestamp": "now",
                            "progress_percentage": output.get("progress_percentage", 0)
                        })
                        logger.debug(f"CAPTURED_PROGRESS: {len(progress_messages)} messages so far")

                    if node_name == "execute_planning" and output.get("formatted_tasks") is not None:
                        plan_event = {
                            "execution_plan": output.get("execution_plan"),
                            "formatted_tasks": output.get("formatted_tasks"),
                            "progress": output.get("progress_percentage", 0),
                            "status": output.get("processing_status", "running"),
                            "message": output.get("progress_message"),
                            "semantic_routing": output.get("semantic_routing"),
                            "current_step": output.get("current_step"),
                            "total_steps": output.get("total_steps")
                        }
                        yield self._create_sse_event(2, "plan", plan_event)

                final_payload = output.get("final_response")
                provider_name = output.get("provider_name")
                processing_status = output.get("processing_status", "completed")
                detected_output_language = output.get("detected_language", detected_language)

                if processing_status == "failed":
                    workflow_status = "failed"
                    pending_error_details = output.get("error_message") or output.get("reasoning")
                    pending_error_response = output.get("final_response") or output.get("error_message")
                    pending_error_sources = output.get("final_sources", [])
                    pending_error_followups = output.get("follow_up_questions", [])
                    pending_error_flow_actions = output.get("flow_action", [])
                    pending_error_execution_metadata = output.get("execution_metadata", {})
                    pending_error_progress = output.get("progress_percentage", 0)

                    if output.get("next_action") == "error" and not final_payload:
                        continue

                if final_payload is not None:
                    status_to_emit = workflow_status if workflow_status != "running" else processing_status
                    error_details = pending_error_details if status_to_emit == "failed" else None
                    output_for_metadata = dict(output)
                    if error_details and "error_message" not in output_for_metadata:
                        output_for_metadata["error_message"] = error_details
                    if not output_for_metadata.get("final_sources") and pending_error_sources:
                        output_for_metadata["final_sources"] = pending_error_sources
                    if not output_for_metadata.get("follow_up_questions") and pending_error_followups:
                        output_for_metadata["follow_up_questions"] = pending_error_followups
                    if not output_for_metadata.get("flow_action") and pending_error_flow_actions:
                        output_for_metadata["flow_action"] = pending_error_flow_actions
                    if pending_error_execution_metadata and not output_for_metadata.get("execution_metadata"):
                        output_for_metadata["execution_metadata"] = pending_error_execution_metadata

                    workflow_metadata = self._create_workflow_metadata(
                        output_for_metadata,
                        progress_messages,
                        "error" if status_to_emit == "failed" else (
                            "response" if status_to_emit == "completed" else status_to_emit
                        ),
                        error_details,
                        detected_output_language
                    )

                    if provider_name:
                        orchestrator = Orchestrator()
                        provider = await orchestrator.llm(provider_name)

                        try:
                            full_response = ""
                            async for stream_event in self._handle_llm_streaming_response(
                                final_payload, provider, tenant_id, session_id, query
                            ):
                                yield stream_event
                                try:
                                    json_str = stream_event.replace('data: ', '').replace('\n\n', '')
                                    event_data = json.loads(json_str)
                                    content_piece = event_data.get('content')
                                    if content_piece:
                                        full_response += content_piece
                                except Exception as e:
                                    logger.error(f"Failed to extract content from streaming event: {e}")

                            model_used = self._get_model_used(provider)

                            follow_up_questions = output_for_metadata.get("follow_up_questions", [])
                            if follow_up_questions:
                                yield self._create_sse_event(4, "followup_question", {
                                    "follow_up_questions": follow_up_questions,
                                    "message": "Generated follow-up questions"
                                })

                            yield self._create_sse_event(5, "end", {
                                "message": "Response completed",
                                "progress": output.get("progress_percentage", 100),
                                "status": status_to_emit,
                                "final_response": full_response.strip(),
                                "sources": output_for_metadata.get("final_sources", []),
                                "reasoning": output.get("reasoning", ""),
                                "confidence_score": output.get("confidence_score", 0.0),
                                "follow_up_questions": output_for_metadata.get("follow_up_questions", []),
                                "flow_action": output_for_metadata.get("flow_action", []),
                                "execution_metadata": output_for_metadata.get("execution_metadata", {})
                            })

                            logger.info(
                                f"SAVING_FINAL_RESPONSE: session_id={session_id}, response_length={len(full_response.strip())}, "
                                f"is_first_message={is_first_message}"
                            )

                            if is_first_message:
                                await self.save_message(
                                    session_id=session_id,
                                    query=query,
                                    response=full_response.strip(),
                                    language=detected_output_language,
                                    model_used=model_used,
                                    chat_metadata={"workflow": workflow_metadata} if workflow_metadata else None
                                )
                            else:
                                chat_metadata = {"workflow": workflow_metadata} if workflow_metadata else None
                                await self.save_message(
                                    session_id=session_id,
                                    query=query,
                                    response=full_response.strip(),
                                    model_used=model_used,
                                    chat_metadata=chat_metadata
                                )
                            final_response_emitted = True
                            return

                        except Exception as stream_err:
                            logger.error(f"LLM streaming failed: {stream_err}")

                            error_response = self._get_error_response(detected_output_language, "general")
                            model_used = f"{self._get_model_used(provider)} (error)"
                            workflow_metadata = self._create_workflow_metadata(
                                output_for_metadata,
                                progress_messages,
                                "error",
                                str(stream_err),
                                detected_output_language
                            )

                            logger.info(
                                f"SAVING_ERROR_RESPONSE: detected_language={detected_output_language}, "
                                f"error={str(stream_err)}, is_first_message={is_first_message}"
                            )

                            if is_first_message:
                                await self.save_message(
                                    session_id=session_id,
                                    query=query,
                                    response=error_response,
                                    language=detected_output_language,
                                    model_used=model_used,
                                    chat_metadata={"workflow": workflow_metadata} if workflow_metadata else None
                                )
                            else:
                                chat_metadata = {"workflow": workflow_metadata} if workflow_metadata else None
                                await self.save_message(
                                    session_id=session_id,
                                    query=query,
                                    response=error_response,
                                    model_used=model_used,
                                    chat_metadata=chat_metadata
                                )

                            yield self._create_sse_event(5, "end", {
                                "message": "Response completed",
                                "progress": output.get("progress_percentage", 100),
                                "status": status_to_emit,
                                "final_response": error_response,
                                "sources": output_for_metadata.get("final_sources", []),
                                "reasoning": f"LLM streaming failed: {str(stream_err)}",
                                "confidence_score": 0.0,
                                "follow_up_questions": output_for_metadata.get("follow_up_questions", []),
                                "flow_action": output_for_metadata.get("flow_action", []),
                                "execution_metadata": output_for_metadata.get("execution_metadata", {})
                            })
                            final_response_emitted = True
                            return

                    else:
                        if isinstance(final_payload, str):
                            final_text = final_payload.strip()
                        else:
                            final_text = json.dumps(final_payload, ensure_ascii=False)

                        yield self._create_sse_event(5, "end", {
                            "message": output.get("progress_message", "Response completed"),
                            "progress": output.get("progress_percentage", 100),
                            "status": status_to_emit,
                            "final_response": final_text,
                            "sources": output_for_metadata.get("final_sources", []),
                            "reasoning": output.get("reasoning", ""),
                            "confidence_score": output.get("confidence_score", 0.0),
                            "follow_up_questions": output_for_metadata.get("follow_up_questions", []),
                            "flow_action": output_for_metadata.get("flow_action", []),
                            "execution_metadata": output_for_metadata.get("execution_metadata", {})
                        })

                        logger.info(
                            f"SAVING_DIRECT_FINAL_RESPONSE: session_id={session_id}, response_length={len(final_text)}, "
                            f"is_first_message={is_first_message}"
                        )

                        if is_first_message:
                            await self.save_message(
                                session_id=session_id,
                                query=query,
                                response=final_text,
                                language=detected_output_language,
                                model_used=output.get("model_used", "workflow"),
                                chat_metadata={"workflow": workflow_metadata} if workflow_metadata else None
                            )
                        else:
                            chat_metadata = {"workflow": workflow_metadata} if workflow_metadata else None
                            await self.save_message(
                                session_id=session_id,
                                query=query,
                                response=final_text,
                                model_used=output.get("model_used", "workflow"),
                                chat_metadata=chat_metadata
                            )
                        final_response_emitted = True
                        return

                elif output.get("processing_status") == "failed":
                    error_response = (
                        pending_error_response
                        or output.get("final_response")
                        or output.get("error_message")
                        or self._get_error_response(detected_output_language, "general")
                    )
                    error_details = pending_error_details or output.get("error_message", "Workflow execution failed")
                    workflow_metadata = self._create_workflow_metadata(
                        output,
                        progress_messages,
                        "error",
                        error_details,
                        detected_output_language
                    )

                    yield self._create_sse_event(5, "end", {
                        "message": output.get("progress_message", "Processing error"),
                        "progress": pending_error_progress or output.get("progress_percentage", 0),
                        "status": "failed",
                        "final_response": error_response,
                        "sources": pending_error_sources or output.get("final_sources", []),
                        "reasoning": error_details,
                        "confidence_score": 0.0,
                        "follow_up_questions": pending_error_followups or output.get("follow_up_questions", []),
                        "flow_action": pending_error_flow_actions or output.get("flow_action", []),
                        "execution_metadata": pending_error_execution_metadata or output.get("execution_metadata", {})
                    })

                    if is_first_message:
                        await self.save_message(
                            session_id=session_id,
                            query=query,
                            response=error_response,
                            language=detected_output_language,
                            model_used=output.get("model_used", "workflow"),
                            chat_metadata={"workflow": workflow_metadata} if workflow_metadata else None
                        )
                    else:
                        chat_metadata = {"workflow": workflow_metadata} if workflow_metadata else None
                        await self.save_message(
                            session_id=session_id,
                            query=query,
                            response=error_response,
                            model_used=output.get("model_used", "workflow"),
                            chat_metadata=chat_metadata
                        )
                    final_response_emitted = True
                    return

            if not final_response_emitted and workflow_status == "failed" and pending_error_response:
                fallback_response = pending_error_response or self._get_error_response(detected_output_language, "general")
                yield self._create_sse_event(5, "end", {
                    "message": "Processing error",
                    "progress": pending_error_progress,
                    "status": "failed",
                    "final_response": fallback_response,
                    "sources": pending_error_sources,
                    "reasoning": pending_error_details or "Workflow execution failed",
                    "confidence_score": 0.0,
                    "follow_up_questions": pending_error_followups,
                    "flow_action": pending_error_flow_actions,
                    "execution_metadata": pending_error_execution_metadata
                })

                workflow_metadata = self._create_workflow_metadata(
                    {
                        "final_sources": pending_error_sources,
                        "follow_up_questions": pending_error_followups,
                        "flow_action": pending_error_flow_actions,
                        "execution_metadata": pending_error_execution_metadata,
                        "progress_percentage": pending_error_progress,
                        "processing_status": "failed"
                    },
                    progress_messages,
                    "error",
                    pending_error_details,
                    detected_output_language
                )

                if is_first_message:
                    await self.save_message(
                        session_id=session_id,
                        query=query,
                        response=fallback_response,
                        language=detected_output_language,
                        model_used="workflow",
                        chat_metadata={"workflow": workflow_metadata} if workflow_metadata else None
                    )
                else:
                    chat_metadata = {"workflow": workflow_metadata} if workflow_metadata else None
                    await self.save_message(
                        session_id=session_id,
                        query=query,
                        response=fallback_response,
                        model_used="workflow",
                        chat_metadata=chat_metadata
                    )
                final_response_emitted = True
                return

        except Exception as e:
            logger.error(f"Multi-agent workflow error: {e}")
            yield self._create_sse_event(5, "end", {
                "message": f"Processing error: {str(e)}",
                "progress": 0,
                "status": "error",
                "error": str(e)
            })

    def _create_sse_event(self, sse_type: int, event_type: str, data: Dict[str, Any]) -> str:
        """Create standardized SSE event with type numbers"""
        import json
        event_data = {
            "sse_type": sse_type,
            "type": event_type,
            **data
        }
        return f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

    def _get_model_used(self, provider) -> str:
        """Extract model name from provider for logging"""
        try:
            prov_name = getattr(provider, 'name', None)
            default_model = getattr(getattr(provider, 'config', None), 'default_model', None)
            if prov_name and default_model:
                return f"{prov_name}:{default_model}"
            else:
                return default_model or prov_name or "unknown"
        except Exception:
            return "unknown"

    def _get_error_response(self, detected_language: str, error_type: str = "general") -> str:
        """Get localized error response based on language"""
        if error_type == "no_provider":
            responses = {
                "vietnamese": "Xin lỗi, hiện tại không có mô hình ngôn ngữ nào khả dụng để xử lý yêu cầu của bạn. Vui lòng thử lại sau.",
                "chinese": "抱歉，目前没有可用的语言模型来处理您的请求。请稍后重试。",
                "japanese": "申し訳ございませんが、現在リクエストを処理できる言語モデルが利用できません。後ほどお試しください。",
                "korean": "죄송합니다. 현재 요청을 처리할 수 있는 언어 모델이 없습니다. 나중에 다시 시도해 주세요."
            }
            return responses.get(detected_language, "I apologize, but no language model is currently available to process your request. Please try again later.")
        else:
            responses = {
                "vietnamese": "Xin lỗi, tôi gặp sự cố kỹ thuật khi xử lý yêu cầu của bạn. Vui lòng thử lại.",
                "chinese": "抱歉，我在处理您的请求时遇到技术问题。请重试。",
                "japanese": "申し訳ございませんが、リクエストの処理中に技術的な問題が発生しました。再度お試しください。",
                "korean": "죄송합니다. 요청을 처리하는 동안 기술적인 문제가 발생했습니다. 다시 시도해 주세요."
            }
            return responses.get(detected_language, "I apologize, but I encountered a technical issue while processing your request. Please try again.")

    def _create_workflow_metadata(self, output: Dict, progress_messages: List, response_type: str = "response",
                                error_details: str = None, detected_language: str = "english") -> Dict:
        """Create standardized workflow metadata"""
        return {
            "reasoning": output.get("reasoning", error_details or ""),
            "execution_metadata": output.get("execution_metadata", {}),
            "sources": output.get("final_sources", []),
            "response_type": response_type,
            "confidence_score": output.get("confidence_score", 0.0),
            "follow_up_questions": output.get("follow_up_questions", []),
            "flow_action": output.get("flow_action", []),
            "detected_language": detected_language,
            "is_chitchat": output.get("is_chitchat", False),
            "processing_status": output.get("processing_status", "completed"),
            "progress_percentage": output.get("progress_percentage", 100),
            "progress_message": output.get("progress_message", ""),
            "progress_messages": progress_messages,
            "semantic_routing": output.get("semantic_routing", {}),
            "agent_responses": output.get("agent_responses", []),
            "conflict_resolution": output.get("conflict_resolution", {}),
            "execution_plan": output.get("execution_plan", {}),
            "agent_providers_loaded": output.get("agent_providers_loaded", 0),
            "error_details": error_details
        }

    async def _handle_llm_streaming_response(self, prompt: str, provider, tenant_id: str, session_id: uuid.UUID, query: str):
        """Handle LLM streaming response for prompts from final response node with connection recovery"""
        try:
            try:
                result = await provider.ainvoke(prompt, tenant_id, markdown=True)
            except Exception as e:
                if "Event loop is closed" in str(e) or "unable to perform operation" in str(e):
                    logger.warning(f"Connection issue detected, retrying with fresh connections: {e}")
                    
                    orchestrator = Orchestrator()
                    fresh_provider = await orchestrator.llm(provider.name)
                    result = await fresh_provider.ainvoke(prompt, tenant_id, markdown=True)
                else:
                    raise

            response_type = "response"

            if inspect.isasyncgen(result) or hasattr(result, "__aiter__"):
                async for chunk_text in result:
                    yield self._create_sse_event(3, "response", {
                        "content": chunk_text,
                        "is_complete": False,
                        "type": response_type
                    })

            elif inspect.isgenerator(result) or (hasattr(result, "__iter__") and not isinstance(result, (str, bytes))):
                for chunk_text in result:
                    yield self._create_sse_event(3, "response", {
                        "content": str(chunk_text),
                        "is_complete": False,
                        "type": response_type
                    })

            else:
                text = result.decode("utf-8", errors="ignore") if isinstance(result, (bytes, bytearray)) else str(result)
                streamed = ""
                for token in text.split():
                    streamed = (streamed + " " + token).strip()
                    yield self._create_sse_event(3, "response", {
                        "content": streamed,
                        "is_complete": False,
                        "type": response_type
                    })
                    await asyncio.sleep(0.02)

        except Exception as e:
            logger.error(f"LLM streaming response failed: {e}")
            raise
