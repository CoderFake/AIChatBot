"""
Session Manager Service  
Simplified session creation and management
Title generation is handled separately by TitleService
"""
from typing import Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from services.chat.chat_service import ChatService
from utils.logging import get_logger

logger = get_logger(__name__)


class SessionManagerService:
    """
    Simplified service for session creation and management
    Title generation is handled separately by TitleService
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.chat_service = ChatService(db)

    async def create_session(
        self,
        user_id: Optional[str],
        tenant_id: str,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new chat session
        """
        try:
            chat_session = await self.chat_service.create_chat_session(
                user_id=user_id,
                tenant_id=tenant_id,
                title=title
            )

            logger.info(f"Created session {chat_session.id}")

            return {
                "session_id": str(chat_session.id),
                "title": chat_session.title,
                "created_at": chat_session.created_at.isoformat(),
                "is_anonymous": chat_session.is_anonymous
            }

        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise

    async def get_or_create_session(
        self,
        session_id_str: Optional[str],
        user_id: Optional[str],
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        Get existing session or create new one
        """
        try:
            chat_session = await self.chat_service.get_or_create_session(
                session_id_str=session_id_str,
                user_id=user_id,
                tenant_id=tenant_id
            )

            logger.info(f"Using session {chat_session.id}")

            return {
                "session_id": str(chat_session.id),
                "title": chat_session.title,
                "created_at": chat_session.created_at.isoformat(),
                "is_anonymous": chat_session.is_anonymous,
                "message_count": chat_session.message_count
            }

        except Exception as e:
            logger.error(f"Failed to get/create session: {e}")
            raise