"""
Authentication Middleware for FastAPI
JWT-based authentication with role verification for Depends()
Integrates AuthService for authentication and ValidatePermission for authorization
"""
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_db
from config.settings import get_settings
from common.types import UserRole, ROLE_LEVEL
from services.auth.auth_service import AuthService
from services.auth.validate_permission import ValidatePermission
from utils.logging import get_logger
from utils.request_utils import get_tenant_identifier_from_request

logger = get_logger(__name__)
settings = get_settings()

security = HTTPBearer()


class JWTAuth:
    """
    JWT authentication handler with AuthService integration
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
        db: AsyncSession = Depends(get_db),
        request: Request = None,
    ) -> Dict[str, Any]:
        """
        Get current user from JWT token with comprehensive validation:
        1. Decode JWT token
        2. Check token blacklist via AuthService
        3. Get user context with tenant/department info
        """
        try:
            token = credentials.credentials
            payload = JWTAuth.decode_token(token)
            
            user_id = payload.get("user_id") or payload.get("sub")
            jti = payload.get("jti")
            
            if not user_id or not jti:
                logger.error("Token missing required fields")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token format"
                )
            
            auth_service = AuthService(db)
            user_context = await auth_service.get_user_context(
                user_id=user_id,
                jti=jti,
                token_data=payload
            )
            
            if not user_context:
                logger.warning(f"User context not found or token blacklisted: {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token"
                )
            
            logger.debug(f"User authenticated: {user_id} with role {user_context.get('role')}")
            return user_context
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
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


class MaintainerOnly:
    """
    Require MAINTAINER role with specific permissions
    Uses AuthService for authentication and ValidatePermission for authorization
    """
    def __init__(self, required_permissions: List[str] = None):
        self.required_permissions = required_permissions or []
    
    async def __call__(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        user_context = await JWTAuth.get_current_user(credentials, db)
        
        user_role = user_context.get("role")
        
        if user_role != UserRole.MAINTAINER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="MAINTAINER role required"
            )

        if self.required_permissions and user_role != UserRole.MAINTAINER.value:
            validate_permission = ValidatePermission(db)
            result = await validate_permission.check_user_has_permissions(
                user_id=user_context.get("user_id"),
                required_permissions=self.required_permissions,
                user_role=user_role,
                require_all=True
            )

            if not result.get("allowed"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=result.get("reason", "Missing required permissions")
                )
            
            user_context.update({
                "validated_permissions": result.get("matched_permissions", []),
                "permission_validation": result
            })
        
        logger.info(f"Maintainer access granted for user {user_context.get('user_id')}")
        return user_context


class AdminOnly:
    """
    Require ADMIN role strictly (no MAINTAINER override) with optional permissions check.
    """
    def __init__(self, required_permissions: List[str] = None):
        self.required_permissions = required_permissions or []
    
    async def __call__(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        user_context = await JWTAuth.get_current_user(credentials, db)
        user_role = user_context.get("role")
        
        if user_role != UserRole.ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ADMIN role required"
            )
        
        if self.required_permissions:
            validate_permission = ValidatePermission(db)
            result = await validate_permission.check_user_has_permissions(
                user_id=user_context.get("user_id"),
                required_permissions=self.required_permissions,
                user_role=user_role,
                require_all=True
            )
            
            if not result.get("allowed"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=result.get("reason", "Missing required permissions")
                )
            
            user_context.update({
                "validated_permissions": result.get("matched_permissions", []),
                "permission_validation": result
            })
        
        logger.info(f"Admin access granted for user {user_context.get('user_id')}")
        return user_context


class DeptAdminOnly:
    """
    Require DEPT_ADMIN role or higher (ADMIN, MAINTAINER) with permissions check
    """
    def __init__(self, required_permissions: List[str] = None):
        self.required_permissions = required_permissions or []
    
    async def __call__(
        self,
        user_context: Dict[str, Any] = Depends(JWTAuth.get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        user_role = user_context.get("role")
        
        # Check role hierarchy
        allowed_roles = [
            UserRole.DEPT_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.MAINTAINER.value
        ]
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="DEPT_ADMIN role or higher required"
            )
        
        if user_role == UserRole.DEPT_ADMIN.value:
            if not user_context.get("department_id"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Department assignment required for DEPT_ADMIN"
                )
        
        if self.required_permissions:
            validate_permission = ValidatePermission(db)
            result = await validate_permission.check_user_has_permissions(
                user_id=user_context.get("user_id"),
                required_permissions=self.required_permissions,
                user_role=user_role,
                require_all=True
            )
            
            if not result.get("allowed"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=result.get("reason", "Missing required permissions")
                )
            
            user_context.update({
                "validated_permissions": result.get("matched_permissions", []),
                "permission_validation": result
            })
        
        logger.info(f"Dept admin access granted for user {user_context.get('user_id')}")
        return user_context


class DeptManagerOnly:
    """
    Require DEPT_MANAGER role or higher with permissions check
    """
    def __init__(self, required_permissions: List[str] = None):
        self.required_permissions = required_permissions or []
    
    async def __call__(
        self,
        user_context: Dict[str, Any] = Depends(JWTAuth.get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        user_role = user_context.get("role")
        
        allowed_roles = [
            UserRole.DEPT_MANAGER.value,
            UserRole.DEPT_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.MAINTAINER.value
        ]
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="DEPT_MANAGER role or higher required"
            )
        
        if user_role not in [UserRole.MAINTAINER.value, UserRole.ADMIN.value]:
            if not user_context.get("department_id"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Department assignment required"
                )
        
        if self.required_permissions:
            validate_permission = ValidatePermission(db)
            result = await validate_permission.check_user_has_permissions(
                user_id=user_context.get("user_id"),
                required_permissions=self.required_permissions,
                user_role=user_role,
                require_all=False 
            )
            
            if not result.get("allowed"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=result.get("reason", "Missing required permissions")
                )
            
            user_context.update({
                "validated_permissions": result.get("matched_permissions", []),
                "permission_validation": result
            })
        
        logger.info(f"Dept manager access granted for user {user_context.get('user_id')}")
        return user_context


class AdminOrDeptAdminOnly:
    """
    Require ADMIN or DEPT_ADMIN roles (MAINTAINER excluded) with permissions check
    """
    def __init__(self, required_permissions: List[str] = None):
        self.required_permissions = required_permissions or []
    
    async def __call__(
        self,
        user_context: Dict[str, Any] = Depends(JWTAuth.get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        user_role = user_context.get("role")
        
        allowed_roles = [UserRole.ADMIN.value, UserRole.DEPT_ADMIN.value]
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ADMIN or DEPT_ADMIN role required"
            )
        
        if user_role == UserRole.DEPT_ADMIN.value:
            if not user_context.get("department_id"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Department assignment required for DEPT_ADMIN"
                )
        
        if self.required_permissions:
            validate_permission = ValidatePermission(db)
            result = await validate_permission.check_user_has_permissions(
                user_id=user_context.get("user_id"),
                required_permissions=self.required_permissions,
                user_role=user_role,
                require_all=True
            )
            
            if not result.get("allowed"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=result.get("reason", "Missing required permissions")
                )
            
            user_context.update({
                "validated_permissions": result.get("matched_permissions", []),
                "permission_validation": result
            })
        
        logger.info(f"Admin/DeptAdmin access granted for user {user_context.get('user_id')}")
        return user_context


# ==================== SINGLE GENERIC ROLE GUARD ====================

class RoleOnly:
    """
    Strict role guard: only the exact role is allowed (no inheritance).
    Optional permissions check (ALL required by default).
    """
    def __init__(self, required_role: str, required_permissions: List[str] | None = None, require_all: bool = True):
        self.required_role = required_role
        self.required_permissions = required_permissions or []
        self.require_all = require_all

    async def __call__(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        user_context = await JWTAuth.get_current_user(credentials, db)
        user_role = user_context.get("role")

        if user_role != self.required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{self.required_role} role required"
            )

        if self.required_permissions and user_role != UserRole.MAINTAINER.value:
            validate_permission = ValidatePermission(db)
            result = await validate_permission.check_user_has_permissions(
                user_id=user_context.get("user_id"),
                required_permissions=self.required_permissions,
                user_role=user_role,
                require_all=self.require_all,
            )
            if not result.get("allowed"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=result.get("reason", "Missing required permissions")
                )
            user_context.update({
                "validated_permissions": result.get("matched_permissions", []),
                "permission_validation": result
            })

        return user_context


class RoleAtLeast:
    """
    Hierarchical role guard: allow min_role or higher (e.g., DeptAdmin -> Admin/Maintainer also allowed).
    Optional permissions check (ALL required by default).
    """
    def __init__(self, min_role: str, required_permissions: List[str] | None = None, require_all: bool = True):
        self.min_role = min_role
        self.required_permissions = required_permissions or []
        self.require_all = require_all

    async def __call__(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        user_context = await JWTAuth.get_current_user(credentials, db)
        user_role = user_context.get("role")

        if ROLE_LEVEL.get(user_role, 0) < ROLE_LEVEL.get(self.min_role, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"{self.min_role} or higher required"
            )

        if self.required_permissions and user_role != UserRole.MAINTAINER.value:
            validate_permission = ValidatePermission(db)
            result = await validate_permission.check_user_has_permissions(
                user_id=user_context.get("user_id"),
                required_permissions=self.required_permissions,
                user_role=user_role,
                require_all=self.require_all,
            )
            if not result.get("allowed"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=result.get("reason", "Missing required permissions")
                )
            user_context.update({
                "validated_permissions": result.get("matched_permissions", []),
                "permission_validation": result
            })

        return user_context


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


class ValidateApiPermission:
    """
    Advanced permission validation for API endpoints
    Complete flow: Authentication -> Authorization
    1. AuthService: Check token blacklist + user status
    2. ValidatePermission: Check endpoint permissions
    """
    
    def __init__(self, endpoint_path: str, http_method: str):
        self.endpoint_path = endpoint_path
        self.http_method = http_method
    
    async def __call__(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Complete validation flow:
        1. JWT decode + token blacklist check + user status (AuthService)
        2. Endpoint permission validation (ValidatePermission)
        """
        try:
            user_context = await JWTAuth.get_current_user(credentials, db)
            user_role = user_context.get("role")

            if user_role == UserRole.MAINTAINER.value:
                validation_result = {
                    "allowed": True,
                    "reason": "MAINTAINER bypass",
                    "user_permissions": ["*"],
                    "validation_type": "maintainer_bypass"
                }
            else:
                validate_permission = ValidatePermission(db)

                validation_result = await validate_permission.validate_api_access(
                    user_id=user_context.get("user_id"),
                    endpoint_path=self.endpoint_path,
                    http_method=self.http_method,
                    user_role=user_role,
                    tenant_id=user_context.get("tenant_id"),
                    department_id=user_context.get("department_id")
                )

                if not validation_result.get("allowed", False):
                    logger.warning(
                        f"API access denied for user {user_context.get('user_id')}: "
                        f"{validation_result.get('reason', 'Unknown reason')}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=validation_result.get("reason", "Access denied")
                    )

            user_context.update({
                "validated_permissions": validation_result.get("user_permissions", []),
                "api_access_validated": True,
                "validation_type": validation_result.get("validation_type", "unknown")
            })

            return user_context
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"API access validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Access validation failed"
            )


class RequirePermission:
    """
    Require specific permission for endpoint access
    Complete flow: Authentication -> Permission Check
    """
    
    def __init__(self, permission_code: str):
        self.permission_code = permission_code
    
    async def __call__(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Check specific permission with authentication
        """
        try:
            user_context = await JWTAuth.get_current_user(credentials, db)
            user_role = user_context.get("role")

            if user_role == UserRole.MAINTAINER.value:
                result = {
                    "allowed": True,
                    "matched_permissions": [self.permission_code],
                    "reason": "MAINTAINER bypass"
                }
            else:
                validate_permission = ValidatePermission(db)

                result = await validate_permission.check_user_has_permissions(
                    user_id=user_context.get("user_id"),
                    required_permissions=[self.permission_code],
                    user_role=user_role,
                    require_all=True,
                    tenant_id=user_context.get("tenant_id")
                )

                if not result.get("allowed"):
                    logger.warning(
                        f"Permission {self.permission_code} denied for user {user_context.get('user_id')}: "
                        f"{result.get('reason', 'Permission check failed')}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Missing required permission: {self.permission_code}"
                    )

            user_context.update({
                "validated_permissions": result.get("matched_permissions", []),
                "permission_validation": result
            })
            
            logger.info(
                f"Permission {self.permission_code} granted for user {user_context.get('user_id')}"
            )
            
            return user_context
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Permission check failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Permission check failed"
            )


# ==================== GLOBAL INSTANCES AND FACTORY FUNCTIONS ====================

jwt_auth = JWTAuth()
require_user = RequireUser()

GetCurrentUser = Depends(jwt_auth.get_current_user)
AuthenticatedUser = Depends(require_user)

def RequireMaintainer(required_permissions: List[str] = None):
    """Factory function for MAINTAINER role with specific permissions"""
    return MaintainerOnly(required_permissions)

def RequireAdmin(required_permissions: List[str] = None):
    """Factory function for ADMIN role (strict) with specific permissions"""
    return AdminOnly(required_permissions)

def RequireDeptAdmin(required_permissions: List[str] = None):
    """Factory function for DEPT_ADMIN role (or higher) with specific permissions"""
    return DeptAdminOnly(required_permissions)

def RequireDeptManager(required_permissions: List[str] = None):
    """Factory function for DEPT_MANAGER role (or higher) with specific permissions"""
    return DeptManagerOnly(required_permissions)

def RequireAdminOrDeptAdmin(required_permissions: List[str] = None):
    """Factory function for ADMIN or DEPT_ADMIN roles (MAINTAINER excluded)."""
    return AdminOrDeptAdminOnly(required_permissions)

def RequireOnlyMaintainer(required_permissions: List[str] = None, require_all: bool = True):
    """Factory function for MAINTAINER role only (strict)"""
    return RoleOnly(UserRole.MAINTAINER.value, required_permissions, require_all)

def RequireOnlyAdmin(required_permissions: List[str] = None, require_all: bool = True):
    """Factory function for ADMIN role only (strict)"""
    return RoleOnly(UserRole.ADMIN.value, required_permissions, require_all)

def RequireOnlyDeptAdmin(required_permissions: List[str] = None, require_all: bool = True):
    """Factory function for DEPT_ADMIN role only (strict)"""
    return RoleOnly(UserRole.DEPT_ADMIN.value, required_permissions, require_all)

def RequireOnlyDeptManager(required_permissions: List[str] = None, require_all: bool = True):
    """Factory function for DEPT_MANAGER role only (strict)"""
    return RoleOnly(UserRole.DEPT_MANAGER.value, required_permissions, require_all)

def RequireAtLeastAdmin(required_permissions: List[str] = None, require_all: bool = True):
    """Factory function for ADMIN role or higher"""
    return RoleAtLeast(UserRole.ADMIN.value, required_permissions, require_all)

def RequireAtLeastDeptAdmin(required_permissions: List[str] = None, require_all: bool = True):
    """Factory function for DEPT_ADMIN role or higher"""
    return RoleAtLeast(UserRole.DEPT_ADMIN.value, required_permissions, require_all)

def RequireAtLeastDeptManager(required_permissions: List[str] = None, require_all: bool = True):
    """Factory function for DEPT_MANAGER role or higher"""
    return RoleAtLeast(UserRole.DEPT_MANAGER.value, required_permissions, require_all)