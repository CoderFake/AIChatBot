"""
Unified Title Service
Handles all title-related operations for chat sessions
"""
import json
import re
import uuid
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from services.orchestrator.orchestrator import Orchestrator
from services.agents.workflow_agent_service import WorkflowAgentService
from utils.logging import get_logger

logger = get_logger(__name__)


class TitleService:
    """
    Unified service for all title-related operations
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.orchestrator = Orchestrator()
        self.workflow_agent_service = WorkflowAgentService(db)

    async def generate_and_update_session_title(
        self,
        session: Any,  
        first_message: str,
        tenant_id: str,
        user_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate title and update session in one operation
        Returns the generated title or None if generation failed
        """
        try:
            if not self._should_generate_title(session, first_message):
                return session.title

            title = await self._generate_title(
                session_id=session.id,
                first_message=first_message,
                tenant_id=tenant_id,
                user_id=user_id
            )

            if title:
                session.title = title
                await self.db.commit()
                await self.db.refresh(session)
                
                logger.info(f"Generated and updated title for session {session.id}: {title}")
                return title
            else:
                logger.warning(f"Title generation failed for session {session.id}")
                return None

        except Exception as e:
            logger.error(f"Failed to generate and update title for session {session.id}: {e}")
            return None

    async def generate_title_only(
        self,
        session_id: uuid.UUID,
        first_message: str,
        tenant_id: str,
        user_id: Optional[str] = None
    ) -> str:
        """
        Generate title only (for API endpoint)
        """
        try:
            title = await self._generate_title(
                session_id=session_id,
                first_message=first_message,
                tenant_id=tenant_id,
                user_id=user_id
            )
            return title or self._create_fallback_title(session_id)
        except Exception as e:
            logger.error(f"Failed to generate title for session {session_id}: {e}")
            return self._create_fallback_title(session_id)

    def _should_generate_title(self, session: Any, first_message: str) -> bool:
        """Check if session needs title generation"""
        if not first_message or not first_message.strip():
            return False
        
        if session.message_count > 0:
            return False
            
        if session.title and not session.title.startswith("Chat"):
            return False
            
        return True

    async def _generate_title(
        self,
        session_id: uuid.UUID,
        first_message: str,
        tenant_id: str,
        user_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Core title generation logic with JSON mode - only use workflow agent provider
        """
        try:
            return await self._generate_title_with_provider(session_id, first_message, tenant_id, None)
        except Exception as primary_error:
            logger.error(f"Title generation failed: {primary_error}")
            raise

    async def _generate_title_with_provider(
        self,
        session_id: uuid.UUID,
        first_message: str,
        tenant_id: str,
        override_provider: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate title with specific provider
        """
        try:
            prompt = f"""Create a short title for this conversation.

Message: {first_message[:200]}...

Keep it under 10 words. Use the same language as the message.

Format: {{"title": "Your title here"}}"""

            if override_provider:
                provider_name = override_provider
            else:
                workflow_agent = await self.workflow_agent_service.get_workflow_agent_config(tenant_id)
                provider_name = workflow_agent.get("provider_name")

            provider = await self.orchestrator.llm(provider_name)

            invoke_params = {
                "prompt": prompt,
                "tenant_id": tenant_id,
                "response_format": "json_object",
                "json_mode": True,
                "temperature": 0.3,
                "max_tokens": 100,
                "system_instruction": "You are a helpful assistant that creates conversation titles. Always respond with valid JSON."
            }

            title_response = await provider.ainvoke(**invoke_params)

            title = self._extract_and_parse_title_json(title_response, first_message, session_id)

            logger.info(f"Generated title for session {session_id} using {provider_name}: {title}")
            return title

        except Exception as e:
            logger.error(f"Title generation failed with provider {provider_name}: {e}")
            raise

    def _extract_and_parse_title_json(self, title_response, first_message: str, session_id: uuid.UUID) -> str:
        """Extract and parse title from JSON response with fallback handling"""
        try:
            # Get content from response
            if hasattr(title_response, 'content'):
                content = title_response.content.strip()
            elif isinstance(title_response, dict) and 'content' in title_response:
                content = title_response['content'].strip()
            elif isinstance(title_response, str):
                content = title_response.strip()
            else:
                content = str(title_response).strip()

            if not content:
                raise RuntimeError("Provider returned empty response for title generation")

            # Parse JSON response
            try:
                json_response = json.loads(content)
                title = json_response.get("title", "").strip()
            except (json.JSONDecodeError, KeyError) as json_err:
                logger.error(f"Failed to parse title JSON: {json_err}")
                # Fallback to regex extraction if JSON parsing fails
                title_match = re.search(r'"title"\s*:\s*"([^"]*)"', content, re.IGNORECASE)
                if title_match:
                    title = title_match.group(1).strip()
                else:
                    raise RuntimeError(f"Could not extract title from response: {content[:200]}")

            # Clean and validate title
            title = self._clean_title_text(title)
            title = self._validate_and_fallback_title(title, first_message, session_id)

            return title

        except Exception as e:
            logger.error(f"Title extraction failed: {e}")
            # Return fallback title
            return self._create_fallback_title(session_id)

    def _clean_title_text(self, title: str) -> str:
        """Clean title text by removing unwanted characters"""
        title = re.sub(r'[*#`]', '', title)
        title = re.sub(r'```.*?```', '', title, flags=re.DOTALL)
        title = re.sub(r'\{.*?\}', '', title)
        return title.strip()

    def _validate_and_fallback_title(self, title: str, first_message: str, session_id: uuid.UUID) -> str:
        """Validate title and create fallback if needed"""
        words = title.split()
        if len(words) > 30:
            title = ' '.join(words[:30])

        if not title or len(title) < 3:
            title = f"Chat about {first_message[:50]}..."

        return title

    def _create_fallback_title(self, session_id: uuid.UUID) -> str:
        """Create fallback title when generation fails"""
        return f"Chat Session {str(session_id)[:8]}"