"""
Authentication Middleware for FastAPI
JWT-based authentication with role verification for Depends()
"""
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_db
from config.settings import get_settings
from common.types import UserRole
from utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

security = HTTPBearer()


class JWTAuth:
    """
    JWT authentication handler
    """
    
    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """
        Decode and validate JWT token
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except JWTError as e:
            logger.error(f"JWT decode error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
    
    @staticmethod
    async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Get current user from JWT token
        Returns user context with role information
        """
        try:
            token = credentials.credentials
            payload = JWTAuth.decode_token(token)
            
            user_id = payload.get("user_id")
            role = payload.get("role")
            tenant_id = payload.get("tenant_id")
            department_id = payload.get("department_id")
            
            if not user_id or not role:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload"
                )
            
            user_context = {
                "user_id": user_id,
                "role": role,
                "tenant_id": tenant_id,
                "department_id": department_id,
                "email": payload.get("email"),
                "username": payload.get("username")
            }
            
            logger.debug(f"Authenticated user: {user_id} with role: {role}")
            return user_context
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication failed"
            )


class RoleRequired:
    """
    Role-based access control for endpoints
    """
    
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles
    
    async def __call__(
        self,
        user_context: Dict[str, Any] = Depends(JWTAuth.get_current_user)
    ) -> Dict[str, Any]:
        """
        Verify user has required role
        """
        user_role = user_context.get("role")
        
        if user_role not in self.allowed_roles:
            logger.warning(
                f"Access denied for user {user_context.get('user_id')} "
                f"with role {user_role}. Required roles: {self.allowed_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {', '.join(self.allowed_roles)}"
            )
        
        return user_context


# Maintenance Role Dependencies
class RequireMaintainer:
    """
    Require MAINTAINER role
    Can manage tenants and global tools
    """
    async def __call__(
        self,
        user_context: Dict[str, Any] = Depends(RoleRequired([UserRole.MAINTAINER.value]))
    ) -> Dict[str, Any]:
        logger.info(f"Maintainer access granted for user {user_context.get('user_id')}")
        return user_context


# Admin Role Dependencies
class RequireAdmin:
    """
    Require ADMIN role
    Can manage departments, users, and department tools
    """
    async def __call__(
        self,
        user_context: Dict[str, Any] = Depends(RoleRequired([UserRole.ADMIN.value]))
    ) -> Dict[str, Any]:
        logger.info(f"Admin access granted for user {user_context.get('user_id')}")
        return user_context


# Department Admin Role Dependencies
class RequireDeptAdmin:
    """
    Require DEPT_ADMIN role (or higher)
    Can configure providers and tools for department
    """
    async def __call__(
        self,
        user_context: Dict[str, Any] = Depends(RoleRequired([
            UserRole.DEPT_ADMIN.value, 
            UserRole.ADMIN.value
        ]))
    ) -> Dict[str, Any]:
        if not user_context.get("department_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Department assignment required"
            )
        logger.info(f"Dept admin access granted for user {user_context.get('user_id')}")
        return user_context


# Department Manager Role Dependencies
class RequireDeptManager:
    """
    Require DEPT_MANAGER role (or higher)
    Can manage documents
    """
    async def __call__(
        self,
        user_context: Dict[str, Any] = Depends(RoleRequired([
            UserRole.DEPT_MANAGER.value,
            UserRole.DEPT_ADMIN.value,
            UserRole.ADMIN.value
        ]))
    ) -> Dict[str, Any]:
        if not user_context.get("department_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Department assignment required"
            )
        logger.info(f"Dept manager access granted for user {user_context.get('user_id')}")
        return user_context


# User Role Dependencies
class RequireUser:
    """
    Require USER role (or any authenticated user)
    Basic user permissions
    """
    async def __call__(
        self,
        user_context: Dict[str, Any] = Depends(JWTAuth.get_current_user)
    ) -> Dict[str, Any]:
        logger.info(f"User access granted for {user_context.get('user_id')}")
        return user_context


jwt_auth = JWTAuth()
require_maintainer = RequireMaintainer()
require_admin = RequireAdmin()
require_dept_admin = RequireDeptAdmin()
require_dept_manager = RequireDeptManager()
require_user = RequireUser()

GetCurrentUser = Depends(jwt_auth.get_current_user)
MaintainerOnly = Depends(require_maintainer)
AdminOnly = Depends(require_admin)
DeptAdminOnly = Depends(require_dept_admin)
DeptManagerOnly = Depends(require_dept_manager)
AuthenticatedUser = Depends(require_user)