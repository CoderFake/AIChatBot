"""
Orchestrator Service - Simplified
Direct workflow system integration
No config, no fallback, no defaults
"""

from typing import Dict, Any, List
from utils.logging import get_logger

logger = get_logger(__name__)


class Orchestrator:
    """
    Simplified orchestrator that directly uses the workflow system
    No configuration management, no fallback logic
    """

    def __init__(self, db=None):
        self.db = db
        self._cache_initialized = False

    async def _ensure_initialized(self):
        """Ensure basic initialization"""
        if not self._cache_initialized:
            self._cache_initialized = True

    async def get_provider_for_tenant(self, tenant_id: str):
        """
        Get LLM provider for tenant
        """
        try:
            from services.llm.provider_manager import get_llm_provider_for_tenant
            return await get_llm_provider_for_tenant(tenant_id)
        except Exception as e:
            logger.error(f"Failed to get provider for tenant {tenant_id}: {e}")
            return None

    async def process_query(
        self,
        query: str,
        messages: List[Dict[str, Any]] = None,
        user_context: Dict[str, Any] = None
    ) -> str:
        """
        Process query using workflow system directly
        """
        try:
            await self._ensure_initialized()

            tenant_id = user_context.get("tenant_id") if user_context else None
            user_id = user_context.get("user_id") if user_context else None

            logger.info(f"Processing query for tenant {tenant_id}, user {user_id}")

            return await self._process_with_workflow(query, messages or [], user_context)

        except ValueError as e:
            raise e
        except Exception as e:
            logger.error(f"Failed to process query: {e}")
            return f"Error processing query: {str(e)}"

    async def process_tenant_query(
        self,
        query: str,
        tenant_id: str,
        user_id: str = None,
        messages: List[Dict[str, Any]] = None,
        use_workflow: bool = True
    ) -> str:
        """
        Process query specifically for a tenant using their workflow configuration
        """
        try:
            await self._ensure_initialized()

            user_context = {
                "tenant_id": tenant_id,
                "user_id": user_id or "anonymous"
            }

            logger.info(f"Processing tenant query for tenant {tenant_id}, user {user_id}")

            if use_workflow:
                return await self._process_with_workflow(query, messages or [], user_context)
            else:
                return await self.process_query(query, messages, user_context)

        except ValueError as e:
            raise e
        except Exception as e:
            logger.error(f"Failed to process tenant query for {tenant_id}: {e}")
            return f"Error processing query for tenant {tenant_id}: {str(e)}"

    async def _process_with_workflow(
        self,
        query: str,
        messages: List[Dict[str, Any]],
        user_context: Dict[str, Any]
    ) -> str:
        """
        Process query using the RAG workflow system with tenant context
        """
        try:
            from workflows.langgraph.workflow_graph import execute_rag_query

            workflow_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        workflow_messages.append({"type": "human", "content": content})
                    elif role == "assistant":
                        workflow_messages.append({"type": "ai", "content": content})

            logger.info(f"Executing RAG workflow for tenant {user_context.get('tenant_id')}")

            result = await execute_rag_query(
                query=query,
                user_context=user_context,
                messages=workflow_messages
            )

            if result and isinstance(result, dict):
                if "final_response" in result:
                    return result["final_response"]
                elif "answer" in result:
                    return result["answer"]
                else:
                    logger.warning(f"No response found in workflow result: {result}")
                    return "I apologize, but I couldn't generate a response for your query."

            return str(result) if result else "No response generated."

        except ValueError as e:
            raise e
        except Exception as e:
            logger.error(f"Failed to process with workflow: {e}")
            return f"Sorry, I encountered an error while processing your request: {str(e)}"

    