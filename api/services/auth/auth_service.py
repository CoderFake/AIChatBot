from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from models.database.user import User
from utils.datetime_utils import DateTimeManager
from utils.logging import get_logger
from services.auth.blacklist_service import TokenBlacklistService
from services.auth.permission_service import PermissionService
from utils.password_utils import verify_password

logger = get_logger(__name__)


class AuthService:
    """
    Authentication service - handles login/logout and token validation
    - User authentication (login/logout)
    - Token blacklist validation
    - User status validation (active, deleted, banned)
    - Session management
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.blacklist_service = TokenBlacklistService(db)
        self.permission_service = PermissionService(db)
    
    async def authenticate_user(self, username: str, password: str, tenant_id: Optional[str] = None, sub_domain: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Authenticate user with username and password
        Only checks authentication, not authorization
        """
        try:
            from sqlalchemy import or_
            query = select(User).where(
                or_(User.username == username, User.email == username),
                User.is_active == True,
                User.is_deleted == False
            )
            if tenant_id:
                query = query.where(User.tenant_id == tenant_id)

            if sub_domain and not tenant_id:
                from models.database.tenant import Tenant
                query = query.join(Tenant, Tenant.id == User.tenant_id, isouter=True).where(Tenant.sub_domain == sub_domain)
            result = await self.db.execute(query)
            user = result.scalar_one_or_none()

            if not user:
                from common.types import UserRole
                fallback_query = select(User).where(
                    or_(User.username == username, User.email == username),
                    User.role == UserRole.MAINTAINER.value,
                    User.is_active == True,
                    User.is_deleted == False
                )
                result = await self.db.execute(fallback_query)
                user = result.scalar_one_or_none()
            
            if not user:
                logger.warning(f"Authentication failed: user not found or inactive - {username}, tenant_id: {tenant_id}, sub_domain: {sub_domain}")
                return None

            if not self._verify_password(password, user.hashed_password):
                logger.warning(f"Authentication failed: invalid password - {username} (tried as username/email)")
                return None
            
            previous_last_login = user.last_login
            user.last_login = await DateTimeManager.tenant_now_cached(str(user.tenant_id) if user.tenant_id else None, self.db)
            await self.db.commit()

            permissions = await self.permission_service.get_user_effective_permissions(str(user.id))

            is_first_login = previous_last_login is None
            force_password_change = is_first_login

            logger.info(f"User authenticated successfully: {username}, first_login: {is_first_login}, force_password_change: {force_password_change}")

            return {
                "user_id": str(user.id),
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "full_name": user.get_full_name(),
                "role": user.role,
                "tenant_id": str(user.tenant_id) if user.tenant_id else None,
                "department_id": str(user.department_id) if user.department_id else None,
                "is_verified": user.is_verified,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "first_login": is_first_login,
                "force_password_change": force_password_change,
                "permissions": permissions
            }
            
        except Exception as e:
            logger.error(f"Authentication error for user {username}: {e}")
            return None
    
    async def validate_user_status(self, user_id: str) -> Dict[str, Any]:
        """
        Validate user status - active, deleted, banned, etc.
        """
        try:
            result = await self.db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                return {
                    "valid": False,
                    "reason": "user_not_found",
                    "message": "User not found"
                }
            
            if user.is_deleted:
                return {
                    "valid": False,
                    "reason": "user_deleted",
                    "message": "User account has been deleted"
                }
            
            if not user.is_active:
                return {
                    "valid": False,
                    "reason": "user_inactive",
                    "message": "User account is inactive"
                }
            
            return {
                "valid": True,
                "user_id": str(user.id),
                "username": user.username,
                "tenant_id": str(user.tenant_id) if user.tenant_id else None
            }
            
        except Exception as e:
            logger.error(f"Error validating user status for {user_id}: {e}")
            return {
                "valid": False,
                "reason": "validation_error",
                "message": "Error validating user status"
            }
    
    async def validate_token(self, jti: str, user_id: str) -> Dict[str, Any]:
        """
        Comprehensive token validation:
        1. Check if token is blacklisted
        2. Check user status
        """
        try:
            is_blacklisted = await self.blacklist_service.is_token_blacklisted(jti)
            if is_blacklisted:
                logger.warning(f"Token validation failed: token blacklisted - JTI: {jti}")
                return {
                    "valid": False,
                    "reason": "token_blacklisted",
                    "message": "Token has been revoked"
                }
            
            user_status = await self.validate_user_status(user_id)
            if not user_status["valid"]:
                logger.warning(f"Token validation failed: {user_status['reason']} - User: {user_id}")
                return user_status
            
            return {
                "valid": True,
                "user_id": user_id,
                "jti": jti
            }
            
        except Exception as e:
            logger.error(f"Token validation error - JTI: {jti}, User: {user_id}, Error: {e}")
            return {
                "valid": False,
                "reason": "validation_error",
                "message": "Error validating token"
            }
    
    async def create_user_session(self, user_id: str, session_data: Dict[str, Any]) -> bool:
        """
        Create user session after successful authentication
        Session timeout uses UTC for consistency across timezones
        """
        try:
            session_data.update({
                "user_id": user_id,
                "created_at": DateTimeManager._now().isoformat(),
                "expires_at": (DateTimeManager._now() + timedelta(hours=24)).isoformat()
            })
            
            logger.info(f"Session created for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create session for user {user_id}: {e}")
            return False
    
    async def logout_user(self, user_id: str, jti: str, token_type: str = "access") -> bool:
        """
        Logout user and blacklist token using UTC timezone
        """
        try:
            expires_at = DateTimeManager._now() + timedelta(days=1)
            success = await self.blacklist_service.blacklist_token(
                jti=jti,
                token_type=token_type,
                user_id=user_id,
                expires_at=expires_at,
                reason="logout"
            )
            
            if success:
                logger.info(f"User logged out: {user_id}, JTI: {jti}")
            
            return success
            
        except Exception as e:
            logger.error(f"Logout failed for user {user_id}: {e}")
            return False
    
    async def is_token_blacklisted(self, jti: str) -> bool:
        """
        Check if token JTI is blacklisted using UTC timezone
        """
        return await self.blacklist_service.is_token_blacklisted(jti)
    
    async def revoke_all_user_tokens(self, user_id: str, reason: str = "admin_revoke") -> bool:
        """
        Revoke all tokens for a user (admin action) using UTC timezone
        """
        return await self.blacklist_service.revoke_all_user_tokens(user_id, reason)
    
    async def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired tokens from blacklist using UTC timezone
        """
        return await self.blacklist_service.cleanup_expired_tokens()
    
    def _verify_password(self, password: str, hashed_password: str) -> bool:
        """
        Verify password against hash
        """
        return verify_password(password, hashed_password)
    
    async def get_user_blacklisted_tokens(self, user_id: str) -> List[dict]:
        """
        Get all blacklisted tokens for a user
        """
        return await self.blacklist_service.get_user_blacklisted_tokens(user_id)
    
    async def get_token_blacklist_stats(self) -> dict:
        """
        Get statistics about token blacklist
        """
        return await self.blacklist_service.get_blacklist_stats()

    async def get_user_context(self, user_id: str, jti: str, token_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Build user context for authenticated requests.

        Flow:
        1) Validate token (blacklist + user status)
        2) Load user from DB (authoritative source)
        3) If role is MAINTAINER, bypass tenant/subdomain scoping
        4) Return minimal context to be enriched by permission validator when needed
        """

        try:
            token_validation = await self.validate_token(jti=jti, user_id=user_id)
            if not token_validation.get("valid"):
                logger.warning(
                    f"get_user_context denied: token invalid - reason={token_validation.get('reason')} user={user_id}"
                )
                return None

            result = await self.db.execute(
                select(User).where(
                    User.id == user_id,
                    User.is_active == True,
                    User.is_deleted == False,
                )
            )
            user: Optional[User] = result.scalar_one_or_none()
            if not user:
                logger.warning(f"get_user_context: user not found or inactive - user={user_id}")
                return None

            token_role = token_data.get("role")
            db_role = user.role
            if token_role and token_role != db_role:
                logger.warning(
                    f"Role mismatch between token and DB: token={token_role} db={db_role} user={user_id}"
                )

            is_maintainer = db_role == getattr(__import__('common.types', fromlist=['UserRole']).types, 'UserRole', None).MAINTAINER.value if False else db_role == 'MAINTAINER'

            context: Dict[str, Any] = {
                "user_id": str(user.id),
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": db_role,
                "tenant_id": None if is_maintainer else (str(user.tenant_id) if user.tenant_id else None),
                "department_id": str(user.department_id) if user.department_id else None,
                "is_verified": user.is_verified,
                "jti": jti,
            }

            return context

        except Exception as e:
            logger.error(f"get_user_context failed for user {user_id}: {e}")
            return None