from sqlalchemy import Column, String, Boolean, Integer, Float, Text, Index, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from models.database.base import BaseModel
from utils.datetime_utils import CustomDateTime


class ChatSession(BaseModel):
    """Model cho chat sessions hỗ trợ anonymous và authenticated users"""
  
    __tablename__ = "chat_sessions"

    user_id = Column(
        String(36),
        nullable=True,
        index=True,
        comment="ID của authenticated user (nullable cho anonymous)"
    )
    
    is_anonymous = Column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="True if it is an anonymous session"
    )
    
    title = Column(
        String(500),
        nullable=True,
        index=True,
        comment="Title of the chat session"
    )

    message_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of messages in the session"
    )
    
    last_activity = Column(
        DateTime(timezone=True),
        nullable=False,
        default=CustomDateTime.now,
        index=True,
        comment="Last activity time"
    )
    
    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at"
    )
    
    __table_args__ = (
        Index('idx_session_user', 'user_id'),
        Index('idx_session_anonymous', 'is_anonymous'),
        Index('idx_session_language', 'language'),
        Index('idx_session_last_activity', 'last_activity'),
    )
    
    @property
    def display_title(self) -> str:
        """Lấy display title, fallback về auto-generated nếu không có"""
        if self.title:
            return self.title
        
        if self.messages:
            first_message = self.messages[0]
            if first_message.content:
                return first_message.content[:50] + "..." if len(first_message.content) > 50 else first_message.content
        
        return f"Chat {str(self.id)[:8]}"
    
    @property
    def is_expired(self) -> bool:
        """Check xem session có expired không"""
        if self.expires_at is None:
            return False
        return CustomDateTime.now() > self.expires_at

    def convert_to_authenticated(self, user_id: str):
        """Convert anonymous session thành authenticated"""
        self.user_id = user_id
        self.is_anonymous = False
    
    def update_activity(self):
        """Update last activity time"""
        self.last_activity = CustomDateTime.now()
    
    def __repr__(self) -> str:
        user_info = f"user_id={self.user_id}" if not self.is_anonymous else f"session_id={self.id}"
        return f"<ChatSession(id={self.id}, {user_info})>"


class ChatMessage(BaseModel):
    """Model cho individual chat messages"""
    
    __tablename__ = "chat_messages"
    
    session_id = Column(
        String(36),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID của chat session"
    )
    
    role = Column(
        String(20),
        nullable=False,
        index=True,
        comment="Role: user, assistant, system"
    )
    
    content = Column(
        Text,
        nullable=False,
        comment="Nội dung message"
    )
    
    language = Column(
        String(10),
        nullable=True,
        comment="Ngôn ngữ của message"
    )
    
    processing_time = Column(
        Float,
        nullable=True,
        comment="Thời gian xử lý (seconds) cho assistant messages"
    )
    
    model_used = Column(
        String(100),
        nullable=True,
        comment="Model đã sử dụng để generate response"
    )
    
    confidence_score = Column(
        Float,
        nullable=True,
        comment="Confidence score của response (0.0 - 1.0)"
    )
    
    chat_metadata = Column(
        JSONB,
        nullable=True,
        comment="Metadata của message"
    )
    
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=CustomDateTime.now,
        comment="Thời điểm tạo message"
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=CustomDateTime.now,
        comment="Thời điểm cập nhật message"
    )

    # Relationships
    session = relationship(
        "ChatSession",
        back_populates="messages"
    )

    __table_args__ = (
        Index('idx_message_session_role', 'session_id', 'role'),
        Index('idx_message_session_created', 'session_id', 'created_at'),
        Index('idx_message_model_used', 'model_used'),
        Index('idx_message_language', 'language'),
    )
    
    @property
    def is_user_message(self) -> bool:
        """Check xem có phải message từ user không"""
        return self.role == "user"
    
    @property
    def is_assistant_message(self) -> bool:
        """Check xem có phải message từ assistant không"""
        return self.role == "assistant"
    
    def __repr__(self) -> str:
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<ChatMessage(id={self.id}, role='{self.role}', content='{content_preview}')>"

