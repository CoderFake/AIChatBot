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
from services.cache.cache_manager import cache_manager
from utils.logging import get_logger
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
        self._cache_initialized = False

    async def _ensure_cache_initialized(self):
        """Ensure cache manager is initialized"""
        if not self._cache_initialized:
            try:
                if not cache_manager._initialized:
                    await cache_manager.initialize()
                self._cache_initialized = True
            except Exception as e:
                logger.warning(f"Cache initialization failed: {e}")
                self._cache_initialized = True

    async def _invalidate_chat_sessions_cache(self, tenant_id: str, user_id: Optional[str]):
        """Invalidate chat sessions cache for a specific user"""
        try:
            await self._ensure_cache_initialized()
            pattern = f"chat_sessions_{tenant_id}_{user_id or 'anonymous'}_*"
            deleted_count = await cache_manager.delete_pattern(pattern)
            if deleted_count > 0:
                logger.info(f"Invalidated {deleted_count} chat session cache keys for user {user_id or 'anonymous'}")
        except Exception as e:
            logger.error(f"Failed to invalidate chat sessions cache: {e}")

    async def _invalidate_chat_messages_cache(self, session_id: str):
        """Invalidate chat messages cache for a specific session"""
        try:
            await self._ensure_cache_initialized()
            pattern = f"chat_messages_{session_id}_*"
            deleted_count = await cache_manager.delete_pattern(pattern)
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

            await self._cache_message(message_data)

            message = ChatMessage(**message_data)

            self.db.add(message)
            await self.db.commit()
            await self.db.refresh(message)

            await self._invalidate_chat_messages_cache(str(session_id))
            await self.invalidate_message_cache(session_id)
            
            await self.update_session_message_count(session_id)

            logger.info(f"Saved message for session {session_id}")
            return message

        except Exception as e:
            logger.error(f"Failed to save message: {e}")
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to save message: {str(e)}")

    async def save_user_query(
        self,
        session_id: uuid.UUID,
        query: str,
        language: Optional[str] = None
    ) -> ChatMessage:
        """
        Save user query (no response yet)
        """
        return await self.save_message(
            session_id=session_id,
            query=query.strip(),
            language=language,
            response=None
        )

    async def save_assistant_response(
        self,
        session_id: uuid.UUID,
        query: str,
        response: str,
        processing_time: Optional[float] = None,
        model_used: Optional[str] = None,
        confidence_score: Optional[float] = None,
        chat_metadata: Optional[Dict[str, Any]] = None,
        workflow_data: Optional[Dict[str, Any]] = None,
        user_message_id: Optional[str] = None
    ) -> ChatMessage:
        """
        Save assistant response with final answer and workflow metadata
        Update existing message by ID if user_message_id provided, otherwise create new
        """
        logger.info(f"SAVE_ASSISTANT_RESPONSE_START: session_id={session_id}, response_length={len(response)}, user_message_id={user_message_id}")
        try:
            from models.database.chat import ChatMessage
            from sqlalchemy import select

            existing_message = None

            if user_message_id:
                stmt = select(ChatMessage).where(ChatMessage.id == user_message_id)
                result = await self.db.execute(stmt)
                existing_message = result.scalar_one_or_none()
                logger.info(f"SEARCH_BY_ID: user_message_id={user_message_id}, found={existing_message is not None}")
           
            if existing_message:
                existing_message.response = response
                if processing_time is not None:
                    existing_message.processing_time = processing_time
                if model_used:
                    existing_message.model_used = model_used
                if confidence_score is not None:
                    existing_message.confidence_score = confidence_score

                if workflow_data:
                    if existing_message.chat_metadata is None:
                        existing_message.chat_metadata = {}
                    existing_message.chat_metadata["workflow"] = workflow_data

                if chat_metadata:
                    if existing_message.chat_metadata is None:
                        existing_message.chat_metadata = {}
                    existing_message.chat_metadata.update(chat_metadata)

                await self.db.flush()
                await self.db.commit()
                message = existing_message
            else:
                if workflow_data:
                    if chat_metadata is None:
                        chat_metadata = {}
                    chat_metadata["workflow"] = workflow_data

                message = await self.save_message(
                    session_id=session_id,
                    query=query,
                    processing_time=processing_time,
                    model_used=model_used,
                    confidence_score=confidence_score,
                    chat_metadata=chat_metadata,
                    response=response
                )

            await self.invalidate_message_cache(session_id)
            logger.info(f"SAVE_ASSISTANT_RESPONSE_SUCCESS: message_id={message.id}, session_id={session_id}")
            return message

        except Exception as e:
            logger.error(f"Failed to save/update assistant response: {e}")
            logger.error(f"SAVE_ASSISTANT_RESPONSE_ERROR_DETAILS: session_id={session_id}, user_message_id={user_message_id}, response_length={len(response) if response else 0}")
            if workflow_data:
                if chat_metadata is None:
                    chat_metadata = {}
                chat_metadata["workflow"] = workflow_data

            return await self.save_message(
                session_id=session_id,
                query=query,
                processing_time=processing_time,
                model_used=model_used,
                confidence_score=confidence_score,
                chat_metadata=chat_metadata,
                response=response
            )

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
            cached_sessions = await cache_manager.get(cache_key)
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

            await cache_manager.set(cache_key, sessions_data, ttl=3600)
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
            cached_messages = await cache_manager.get(cache_key)
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

            await cache_manager.set(cache_key, messages_data, ttl=3600)
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
            cached_messages = await cache_manager.get(cache_key)
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

            await cache_manager.set(cache_key, recent_messages, ttl=3600)
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
            await cache_manager.delete(cache_key)
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

            await cache_manager.set(cache_key, message_data, ttl=3600) 
            logger.debug(f"Cached message for session {session_id}")
        except Exception as e:
            logger.warning(f"Failed to cache message: {e}")

    async def enrich_user_context(self, user_context: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
        """
        Enrich user context with tenant information using cached timezone lookup
        """
        try:
            from utils.datetime_utils import DateTimeManager
            
            tenant_timezone = await DateTimeManager._get_tenant_timezone_cached(tenant_id, self.db)
            user_context["timezone"] = tenant_timezone
            logger.debug(f"Using tenant timezone: {tenant_timezone}")
            
            return user_context
            
        except Exception as e:
            logger.warning(f"Failed to enrich user context with tenant timezone: {e}")
            user_context["timezone"] = "UTC"
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
        session_id: uuid.UUID,
        tenant_id: str,
        department_id: Optional[str],
        user_context: Dict[str, Any],
        detected_language: str,
        user_message_id: str,
        session_title: Optional[str] = None
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
                    "access_scope": user_context.get("access_scope")
                }
            )

            final_response = ""
            progress_messages = [] 

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
                tenant_description=""
            ):
                if chunk.get("type") == "node":
                    node_name = chunk.get("node", "")
                    output = chunk.get("output", {})

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

                        if node_name == "final_response":
                            final_response = output.get("final_response", "")
                            provider = output.get("provider")

                            if final_response and provider:
                                try:
                                    full_response = ""
                                    async for stream_event in self._handle_llm_streaming_response(
                                        final_response, provider, session_id, query
                                    ):
                                        yield stream_event
                                        try:
                                            json_str = stream_event.replace('data: ', '').replace('\n\n', '')
                                            event_data = json.loads(json_str)
                                            content_piece = event_data.get('content')
                                            if content_piece and not self._is_template_scaffold(content_piece):
                                                full_response += content_piece
                                        except Exception as e:
                                            logger.error(f"Failed to extract content from streaming event: {e}")
                                            pass

                                    try:
                                        model_used = None
                                        try:
                                            prov_name = getattr(provider, 'name', None)
                                            default_model = getattr(getattr(provider, 'config', None), 'default_model', None)
                                            if prov_name and default_model:
                                                model_used = f"{prov_name}:{default_model}"
                                            else:
                                                model_used = default_model or prov_name or "unknown"
                                        except Exception:
                                            model_used = "unknown"

                                        workflow_metadata = {
                                            "reasoning": output.get("reasoning", ""),
                                            "execution_metadata": output.get("execution_metadata", {}),
                                            "sources": output.get("final_sources", []),
                                            "response_type": "response",
                                            "confidence_score": output.get("confidence_score", 0.0),
                                            "follow_up_questions": output.get("follow_up_questions", []),
                                            "flow_action": output.get("flow_action", []),
                                            "detected_language": output.get("detected_language", "english"),
                                            "is_chitchat": output.get("is_chitchat", False),
                                            "processing_status": output.get("processing_status", "completed"),
                                            "progress_percentage": output.get("progress_percentage", 100),
                                            "progress_message": output.get("progress_message", ""),
                                            "progress_messages": [], 
                                            "semantic_routing": output.get("semantic_routing", {}),
                                            "agent_responses": output.get("agent_responses", []),
                                            "conflict_resolution": output.get("conflict_resolution", {}),
                                            "execution_plan": output.get("execution_plan", {}),
                                            "agent_providers_loaded": output.get("agent_providers_loaded", 0)
                                        }

                                        logger.info(f"SAVING_FINAL_RESPONSE: session_id={session_id}, response_length={len(full_response.strip())}, user_message_id={user_message_id}")
                                        await self.save_assistant_response(
                                            session_id=session_id,
                                            query=query,
                                            response=full_response.strip(),
                                            model_used=model_used,
                                            workflow_data=workflow_metadata,
                                            user_message_id=user_message_id
                                        )
                                        logger.info(f"SUCCESSFULLY_SAVED_FINAL_RESPONSE: session_id={session_id}")
                                    except Exception as save_err:
                                        logger.error(f"Failed to save assistant response: {save_err}")

                                    yield self._create_sse_event(4, "end", {
                                        "message": "Response completed",
                                        "progress": 100,
                                        "status": "completed",
                                        "final_response": full_response.strip(),
                                        "sources": output.get("final_sources", []),
                                        "reasoning": output.get("reasoning", ""),
                                        "confidence_score": output.get("confidence_score", 0.0),
                                        "follow_up_questions": output.get("follow_up_questions", []),
                                        "flow_action": output.get("flow_action", []),
                                        "execution_metadata": output.get("execution_metadata", {})
                                    })
                                    return
                                except Exception as stream_err:
                                    logger.error(f"LLM streaming failed: {stream_err}")
                                    try:
                                        model_used = None
                                        try:
                                            prov_name = getattr(provider, 'name', None)
                                            default_model = getattr(getattr(provider, 'config', None), 'default_model', None)
                                            if prov_name and default_model:
                                                model_used = f"{prov_name}:{default_model}"
                                            else:
                                                model_used = default_model or prov_name or "unknown"
                                        except Exception:
                                            model_used = "unknown"

                                        workflow_metadata = {
                                            "reasoning": output.get("reasoning", ""),
                                            "execution_metadata": output.get("execution_metadata", {}),
                                            "sources": output.get("final_sources", []),
                                            "response_type": "response",
                                            "confidence_score": output.get("confidence_score", 0.0),
                                            "follow_up_questions": output.get("follow_up_questions", []),
                                            "flow_action": output.get("flow_action", []),
                                            "detected_language": output.get("detected_language", "english"),
                                            "is_chitchat": output.get("is_chitchat", False),
                                            "processing_status": output.get("processing_status", "completed"),
                                            "progress_percentage": output.get("progress_percentage", 100),
                                            "progress_message": output.get("progress_message", ""),
                                            "progress_messages": progress_messages,
                                            "semantic_routing": output.get("semantic_routing", {}),
                                            "agent_responses": output.get("agent_responses", []),
                                            "conflict_resolution": output.get("conflict_resolution", {}),
                                            "execution_plan": output.get("execution_plan", {}),
                                            "agent_providers_loaded": output.get("agent_providers_loaded", 0)
                                        }
                                        logger.info(f"SAVING_RESPONSE: progress_messages_count={len(progress_messages)}, detected_language={output.get('detected_language', 'unknown')}")
                                        await self.save_assistant_response(
                                            session_id=session_id,
                                            query=query,
                                            response=final_response,
                                            model_used=model_used,
                                            workflow_data=workflow_metadata,
                                            user_message_id=user_message_id
                                        )
                                    except Exception as save_err:
                                        logger.error(f"Failed to save assistant response (fallback): {save_err}")

                                    yield self._create_sse_event(4, "end", {
                                        "message": "Response completed",
                                        "progress": 100,
                                        "status": "completed",
                                        "final_response": final_response,
                                        "sources": output.get("final_sources", []),
                                        "reasoning": output.get("reasoning", ""),
                                        "confidence_score": output.get("confidence_score", 0.0),
                                        "follow_up_questions": output.get("follow_up_questions", []),
                                        "flow_action": output.get("flow_action", []),
                                        "execution_metadata": output.get("execution_metadata", {})
                                    })
                                    return

                            try:
                                workflow_metadata = {
                                    "reasoning": output.get("reasoning", ""),
                                    "execution_metadata": output.get("execution_metadata", {}),
                                    "sources": output.get("final_sources", []),
                                    "response_type": "response",
                                    "progress_messages": progress_messages,
                                    "agent_responses": output.get("agent_responses", []),
                                    "semantic_routing": output.get("semantic_routing", {}),
                                    "execution_plan": output.get("execution_plan", {}),
                                    "processing_status": "completed",
                                    "progress_percentage": 100
                                }
                                await self.save_assistant_response(
                                    session_id=session_id,
                                    query=query,
                                    response=(final_response or ""),
                                    model_used=None,
                                    workflow_data=workflow_metadata,
                                    user_message_id=user_message_id
                                )
                            except Exception as save_err:
                                logger.error(f"Failed to save assistant response (no provider): {save_err}")

                            yield self._create_sse_event(4, "end", {
                                "message": "Response completed",
                                "progress": 100,
                                "status": "completed",
                                "final_response": final_response or "Hello! How can I help you today?",
                                "sources": output.get("final_sources", []),
                                "reasoning": output.get("reasoning", ""),
                                "confidence_score": output.get("confidence_score", 0.0),
                                "follow_up_questions": output.get("follow_up_questions", []),
                                "flow_action": output.get("flow_action", []),
                                "execution_metadata": output.get("execution_metadata", {})
                            })
                        else:
                            evt = self._map_node_to_sse_event(node_name, output)
                            if evt:
                                event_type, sse_type, data = evt
                                yield self._create_sse_event(sse_type, event_type, data)
                            continue
        except Exception as e:
            logger.error(f"Multi-agent workflow error: {e}")
            yield self._create_sse_event(4, "end", {
                "message": f"Processing error: {str(e)}",
                "progress": 0,
                "status": "error",
                "error": str(e)
            })

    def _map_node_to_sse_event(self, node_name: str, output: Dict[str, Any]) -> Optional[tuple]:
        """Map LangGraph node to SSE event format"""

        if output.get("chitchat_response"):
            return ("chitchat_response", 3, {
                "message": "Chitchat response generated",
                "progress": 100,
                "status": "completed",
                "content": output.get("chitchat_response")
            })

        if node_name == "execute_planning":
            progress = output.get("progress_percentage", 0)
            if output.get("processing_status") == "plan_ready":
                progress = 0
            return ("plan_execution", 2, {
                "message": output.get("progress_message", "Planning execution"),
                "progress": progress,
                "status": output.get("processing_status", "running"),
                "execution_plan": output.get("execution_plan", {})
            })

        if node_name == "final_response":
            final_response = output.get("final_response", "")
            return ("end", 4, {
                "message": "Response completed",
                "progress": 100,
                "status": "completed",
                "final_response": final_response,
                "sources": output.get("final_sources", []),
                "reasoning": output.get("reasoning", ""),
                "confidence_score": output.get("confidence_score", 0.0),
                "follow_up_questions": output.get("follow_up_questions", []),
                "flow_action": output.get("flow_action", []),
                "execution_metadata": output.get("execution_metadata", {})
            })

        return None

    def _create_sse_event(self, sse_type: int, event_type: str, data: Dict[str, Any]) -> str:
        """Create standardized SSE event with type numbers"""
        import json
        event_data = {
            "sse_type": sse_type,
            "type": event_type,
            **data
        }
        return f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

    def _is_template_scaffold(self, text: str) -> bool:
        """Filter out template/prompt scaffolding chunks so FE doesn't see raw prompt."""
        if not text:
            return False
        lowered = text.lower()
        scaffolds = [
            "you are ",
            "conversation history:",
            "current user message:",
            "instructions:",
            "generate only the response",
            "no additional formatting",
            "respond naturally in",
        ]
        return any(s in lowered for s in scaffolds)

    async def _handle_llm_streaming_response(self, prompt: str, provider, session_id: uuid.UUID, query: str):
        """Handle LLM streaming response for prompts from final response node"""
        try:
            result = await provider.ainvoke(prompt, markdown=True)
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
