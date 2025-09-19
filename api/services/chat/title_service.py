"""
Unified Title Service
Handles all title-related operations for chat sessions
"""
import re
import uuid
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession

from services.orchestrator.orchestrator import Orchestrator
from utils.logging import get_logger
from utils.language_utils import detect_language
from utils.prompt_utils import PromptUtils

logger = get_logger(__name__)


class TitleService:
    """
    Unified service for all title-related operations
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.orchestrator = Orchestrator(db=db)

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
        Core title generation logic
        """
        try:
            detected_language = detect_language(first_message)
            
            language_instruction = PromptUtils.get_language_instruction(detected_language)
            
            system_prompt = f"""You are creating a conversation title that helps users organize their chat history.

{language_instruction}

Rules for creating titles:
- Create a natural, conversational title (5-15 words maximum)
- Focus on the main topic, question, or intent
- Use simple, everyday language 
- Avoid meta-commentary like "(không có nội dung cụ thể)" or explanatory phrases
- Make it specific enough to be memorable
- Think like a human organizing their conversations

Examples of GOOD titles:
- "Hỏi về thời tiết hôm nay"
- "Cách nấu phở bò"  
- "Giải thích machine learning"
- "Lịch trình du lịch Đà Nẵng"

Examples of BAD titles:
- "Chào buổi sáng (không có nội dung cụ thể)"
- "Cuộc trò chuyện về nhiều chủ đề khác nhau"
- "Người dùng hỏi một câu hỏi"

Return ONLY the title, nothing else."""

            user_prompt = self._build_user_prompt(first_message, detected_language)

            combined_prompt = f"{system_prompt}\n\n{user_prompt}"

            provider = await self.orchestrator.get_provider_for_tenant(tenant_id)
            if not provider:
                logger.error(f"No provider available for tenant {tenant_id}")
                return None

            title_response = await provider.ainvoke(
                prompt=combined_prompt,
                temperature=0.1,
                max_tokens=100
            )

            title = self._extract_clean_title(title_response)
            title = self._validate_and_fallback_title(title, first_message, session_id)

            logger.info(f"Generated title for session {session_id}: {title}")
            return title

        except Exception as e:
            logger.error(f"Title generation failed for session {session_id}: {e}")
            return None

    def _build_user_prompt(self, first_message: str, detected_language: str) -> str:
        """Build user prompt based on detected language"""
        if detected_language == "vietnamese":
            return f"Tin nhắn đầu tiên: \"{first_message}\"\n\nTạo tiêu đề ngắn gọn, tự nhiên cho cuộc trò chuyện này:"
        elif detected_language == "japanese":
            return f"最初のメッセージ: \"{first_message}\"\n\nこの会話の簡潔で自然なタイトルを作成してください："
        elif detected_language == "korean":
            return f"첫 번째 메시지: \"{first_message}\"\n\n이 대화의 간결하고 자연스러운 제목을 만들어주세요:"
        elif detected_language == "chinese":
            return f"第一条消息: \"{first_message}\"\n\n为这次对话创建一个简洁自然的标题："
        else:
            return f"First message: \"{first_message}\"\n\nCreate a concise, natural title for this conversation:"

    def _extract_clean_title(self, title_response) -> str:
        """Extract clean title from LLM response"""
        if hasattr(title_response, 'content'):
            title = title_response.content.strip()
        elif isinstance(title_response, dict) and 'content' in title_response:
            title = title_response['content'].strip()
        elif isinstance(title_response, str):
            title = title_response.strip()
        else:
            title = str(title_response).strip()

        title = re.sub(r'[*#`]', '', title)  
        title = re.sub(r'```.*?```', '', title, flags=re.DOTALL)  
        title = re.sub(r'\{.*?\}', '', title)  
        title = title.strip()

        return title

    def _validate_and_fallback_title(self, title: str, first_message: str, session_id: uuid.UUID) -> str:
        """Validate title and create fallback if needed"""
        # Limit to 30 words
        words = title.split()
        if len(words) > 30:
            title = ' '.join(words[:30])

        if not title or len(title) < 3:
            title = f"Chat about {first_message[:50]}..."

        return title

    def _create_fallback_title(self, session_id: uuid.UUID) -> str:
        """Create fallback title when generation fails"""
        return f"Chat Session {str(session_id)[:8]}"
