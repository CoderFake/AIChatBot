from sqlalchemy import Column, String, Boolean, Integer, Float, Text, Index, ForeignKey, DateTime, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from models.database.base import BaseModel
from utils.datetime_utils import DateTimeManager


class ChatSession(BaseModel):
    """Model for chat sessions to anonymous and authenticated users""" 
  
    __tablename__ = "chat_sessions"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID of authenticated user (nullable for anonymous)"
    )

    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Tenant ID for multi-tenancy"
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
        default=DateTimeManager._now,
        index=True,
        comment="Last activity time"
    )
    
    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at"
    )

    user = relationship(
        "User",
        back_populates="chat_sessions"
    )

    tenant = relationship(
        "Tenant",
        back_populates="chat_sessions"
    )
    
    __table_args__ = (
        Index('idx_session_user', 'user_id'),
        Index('idx_session_tenant', 'tenant_id'),
        Index('idx_session_anonymous', 'is_anonymous'),
        Index('idx_session_last_activity', 'last_activity'),
        Index('idx_session_tenant_last_activity', 'tenant_id', 'last_activity'),
    )
    
    @property
    def display_title(self) -> str:
        """Get display title, fallback to auto-generated if no title"""
        if self.title:
            return self.title
        
        if self.messages:
            first_message = self.messages[0]
            if first_message.content:
                return first_message.content[:50] + "..." if len(first_message.content) > 50 else first_message.content
        
        return f"Chat {str(self.id)[:8]}"
    
    @property
    def is_expired(self) -> bool:
        """Check if session is expired"""
        if self.expires_at is None:
            return False
        return DateTimeManager._now() > self.expires_at

    def convert_to_authenticated(self, user_id: str):
        """Convert anonymous session to authenticated"""
        self.user_id = user_id
        self.is_anonymous = False
    
    def update_activity(self):
        """Update last activity time"""
        self.last_activity = DateTimeManager._now()
    
    def __repr__(self) -> str:
        user_info = f"user_id={self.user_id}" if not self.is_anonymous else f"session_id={self.id}"
        return f"<ChatSession(id={self.id}, {user_info})>"


class ChatMessage(BaseModel):
    """Model for individual chat messages"""
    
    __tablename__ = "chat_messages"
    
    session_id = Column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID of chat session"
    )
    
    query = Column(
        Text,
        nullable=False,
        comment="User query"
    )

    response = Column(
        Text,
        nullable=True,
        comment="Final AI response for user question"
    )

    language = Column(
        String(10),
        nullable=True,
        comment="Language of message"
    )
    
    processing_time = Column(
        Float,
        nullable=True,
        comment="Processing time (seconds) for assistant messages"
    )
    
    model_used = Column(
        String(100),
        nullable=True,
        comment="Model used to generate response"
    )
    
    confidence_score = Column(
        Float,
        nullable=True,
        comment="Confidence score of response (0.0 - 1.0)"
    )
    
    chat_metadata = Column(
        JSONB,
        nullable=True,
        comment="Metadata of message"
    )

    session = relationship(
        "ChatSession",
        back_populates="messages"
    )

    __table_args__ = (
        Index('idx_message_session_created', 'session_id', 'created_at'),
        Index('idx_message_model_used', 'model_used'),
        Index('idx_message_language', 'language'),
    )
    
    @property
    def is_user_query(self) -> bool:
        """Check if message is user query (no response)"""
        return self.response is None or self.response == ""

    @property
    def is_ai_response(self) -> bool:
        """Check if message has AI response"""
        return self.response is not None and self.response != ""
    
    def __repr__(self) -> str:
        query_preview = self.query[:50] + "..." if len(self.query) > 50 else self.query
        return f"<ChatMessage(id={self.id}, query='{query_preview}', has_response={self.is_ai_response})>"

