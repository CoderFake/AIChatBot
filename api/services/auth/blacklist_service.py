"""
Token Blacklist Service
Manages token blacklisting and validation for security
All token operations use UTC timezone for consistency
"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_
from datetime import datetime, timedelta

from models.database.user import TokenBlacklist
from utils.datetime_utils import DateTimeManager
from utils.logging import get_logger

logger = get_logger(__name__)


class TokenBlacklistService:
    """
    Service for managing token blacklist operations
    All token operations use UTC timezone to prevent timezone-related validation errors
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def blacklist_token(
        self, 
        jti: str, 
        token_type: str, 
        user_id: str, 
        expires_at: datetime,
        reason: str = "logout"
    ) -> bool:
        """
        Add token to blacklist using UTC timezone
        """
        try:
            blacklist_entry = TokenBlacklist(
                jti=jti,
                token_type=token_type,
                user_id=user_id,
                expires_at=expires_at,
                reason=reason
            )
            
            self.db.add(blacklist_entry)
            await self.db.commit()
            
            logger.info(f"Token blacklisted: JTI={jti}, user={user_id}, reason={reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to blacklist token {jti}: {e}")
            await self.db.rollback()
            return False
    
    async def is_token_blacklisted(self, jti: str) -> bool:
        """
        Check if token is blacklisted using UTC timezone comparison
        """
        try:
            result = await self.db.execute(
                select(TokenBlacklist).where(
                    and_(
                        TokenBlacklist.jti == jti,
                        TokenBlacklist.expires_at > DateTimeManager._now()
                    )
                )
            )
            
            blacklisted = result.scalar_one_or_none() is not None
            
            if blacklisted:
                logger.debug(f"Token {jti} is blacklisted")
            
            return blacklisted
            
        except Exception as e:
            logger.error(f"Error checking token blacklist for {jti}: {e}")
            return True
    
    async def revoke_all_user_tokens(self, user_id: str, reason: str = "admin_revoke") -> bool:
        """
        Revoke all tokens for a user using UTC timezone
        """
        try:
            revoke_entry = TokenBlacklist(
                jti=f"revoke_all_{user_id}_{int(DateTimeManager._now().timestamp())}",
                token_type="revoke_all",
                user_id=user_id,
                expires_at=DateTimeManager._now() + timedelta(days=30),
                reason=reason
            )
            
            self.db.add(revoke_entry)
            await self.db.commit()
            
            logger.info(f"Revoked all tokens for user {user_id}, reason: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to revoke all tokens for user {user_id}: {e}")
            await self.db.rollback()
            return False
    
    async def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired tokens from blacklist using UTC timezone
        """
        try:
            current_time = DateTimeManager._now()
            
            result = await self.db.execute(
                delete(TokenBlacklist).where(
                    TokenBlacklist.expires_at <= current_time
                )
            )
            
            await self.db.commit()
            deleted_count = result.rowcount
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired tokens")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Token cleanup failed: {e}")
            await self.db.rollback()
            return 0
    
    async def get_user_blacklisted_tokens(self, user_id: str) -> List[dict]:
        """
        Get all blacklisted tokens for a user
        """
        try:
            result = await self.db.execute(
                select(TokenBlacklist).where(
                    and_(
                        TokenBlacklist.user_id == user_id,
                        TokenBlacklist.expires_at > DateTimeManager._now()
                    )
                ).order_by(TokenBlacklist.created_at.desc())
            )
            
            tokens = result.scalars().all()
            
            return [
                {
                    "jti": token.jti,
                    "token_type": token.token_type,
                    "reason": token.reason,
                    "expires_at": token.expires_at.isoformat(),
                    "created_at": token.created_at.isoformat()
                }
                for token in tokens
            ]
            
        except Exception as e:
            logger.error(f"Failed to get blacklisted tokens for user {user_id}: {e}")
            return []
    
    async def get_blacklist_stats(self) -> dict:
        """
        Get statistics about token blacklist
        """
        try:
            current_time = DateTimeManager._now()
            
            active_result = await self.db.execute(
                select(TokenBlacklist).where(
                    TokenBlacklist.expires_at > current_time
                )
            )
            active_count = len(active_result.scalars().all())
            
            expired_result = await self.db.execute(
                select(TokenBlacklist).where(
                    TokenBlacklist.expires_at <= current_time
                )
            )
            expired_count = len(expired_result.scalars().all())
            
            return {
                "active_blacklisted_tokens": active_count,
                "expired_tokens": expired_count,
                "total_tokens": active_count + expired_count,
                "last_checked": current_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get blacklist stats: {e}")
            return {
                "active_blacklisted_tokens": 0,
                "expired_tokens": 0,
                "total_tokens": 0,
                "error": str(e)
            }