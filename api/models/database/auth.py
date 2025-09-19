from sqlalchemy import Column, String, Boolean, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import text
from models.database.base import BaseModel


class UserActionToken(BaseModel):
    """
    Unified action tokens: invite | reset
    - token_hash: SHA-256 digest of opaque token
    - token_type: 'invite' or 'reset'
    - email: for invite (target email)
    - user_id: for reset (target user)
    - tenant_id, role: for invite context
    - used, expires_at: lifecycle control
    """
    __tablename__ = "user_action_tokens"

    token_hash = Column(String(128), nullable=False, index=True)
    token_type = Column(String(20), nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    role = Column(String(50), nullable=True)
    used = Column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    expires_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('idx_user_action_token', 'token_type', 'token_hash'),
    )


