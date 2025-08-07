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
from services.auth.validate_permission import ValidatePermission
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
    
    @staticmethod
    async def validate_api_access(
        user_context: Dict[str, Any],
        endpoint_path: str,
        http_method: str,
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Validate if user can access specific API endpoint
        Uses ValidatePermission to check detailed permissions
        """
        try:
            validate_permission = ValidatePermission(db)
            
            validation_result = await validate_permission.validate_api_access(
                user_id=user_context.get("user_id"),
                endpoint_path=endpoint_path,
                http_method=http_method,
                user_role=user_context.get("role"),
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
class MaintainerOnly:
    """
    Require MAINTAINER role with specific permissions
    """
    def __init__(self, required_permissions: List[str] = None):
        self.required_permissions = required_permissions or []
    
    async def __call__(
        self,
        user_context: Dict[str, Any] = Depends(JWTAuth.get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        user_role = user_context.get("role")
        
        # Check role hierarchy first
        if user_role != UserRole.MAINTAINER.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="MAINTAINER role required"
            )
        
        # Check specific permissions if provided
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
        
        logger.info(f"Maintainer access granted for user {user_context.get('user_id')}")
        return user_context


class AdminOnly:
    """
    Require ADMIN role (or higher) with specific permissions
    """
    def __init__(self, required_permissions: List[str] = None):
        self.required_permissions = required_permissions or []
    
    async def __call__(
        self,
        user_context: Dict[str, Any] = Depends(JWTAuth.get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        user_role = user_context.get("role")
        
        # Check role hierarchy - MAINTAINER can also access ADMIN endpoints
        allowed_roles = [UserRole.ADMIN.value, UserRole.MAINTAINER.value]
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ADMIN role or higher required"
            )
        
        # Check specific permissions if provided
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
    Require DEPT_ADMIN role (or higher) with specific permissions
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
        allowed_roles = [UserRole.DEPT_ADMIN.value, UserRole.ADMIN.value, UserRole.MAINTAINER.value]
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="DEPT_ADMIN role or higher required"
            )
        
        # Check department assignment for non-global roles
        if user_role not in [UserRole.MAINTAINER.value, UserRole.ADMIN.value]:
            if not user_context.get("department_id"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Department assignment required"
                )
        
        # Check specific permissions if provided
        if self.required_permissions:
            validate_permission = ValidatePermission(db)
            result = await validate_permission.check_user_has_permissions(
                user_id=user_context.get("user_id"),
                required_permissions=self.required_permissions,
                user_role=user_role,
                require_all=False  # DeptAdmin might need ANY of the permissions
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
    Require DEPT_MANAGER role (or higher) with specific permissions
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
        
        # Check department assignment for non-global roles
        if user_role not in [UserRole.MAINTAINER.value, UserRole.ADMIN.value]:
            if not user_context.get("department_id"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Department assignment required"
                )
        
        # Check specific permissions if provided
        if self.required_permissions:
            validate_permission = ValidatePermission(db)
            result = await validate_permission.check_user_has_permissions(
                user_id=user_context.get("user_id"),
                required_permissions=self.required_permissions,
                user_role=user_role,
                require_all=False  # DeptManager might need ANY of the permissions
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
    Uses ValidatePermission class for detailed permission checking
    """
    
    def __init__(self, endpoint_path: str, http_method: str):
        self.endpoint_path = endpoint_path
        self.http_method = http_method
    
    async def __call__(
        self,
        user_context: Dict[str, Any] = Depends(JWTAuth.get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Validate API access with detailed permission checking
        """
        try:
            validate_permission = ValidatePermission(db)
            
            validation_result = await validate_permission.validate_api_access(
                user_id=user_context.get("user_id"),
                endpoint_path=self.endpoint_path,
                http_method=self.http_method,
                user_role=user_context.get("role"),
                tenant_id=user_context.get("tenant_id"),
                department_id=user_context.get("department_id")
            )
            
            if not validation_result.get("allowed", False):
                logger.warning(
                    f"Permission denied for user {user_context.get('user_id')} "
                    f"on {self.http_method} {self.endpoint_path}: "
                    f"{validation_result.get('reason', 'Unknown reason')}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=validation_result.get("reason", "Access denied")
                )
            
            # Add validation info to user context
            user_context.update({
                "validated_permissions": validation_result.get("user_permissions", []),
                "permission_validation": validation_result,
                "endpoint_validated": f"{self.http_method} {self.endpoint_path}"
            })
            
            logger.info(
                f"Permission validation passed for user {user_context.get('user_id')} "
                f"on {self.http_method} {self.endpoint_path}"
            )
            
            return user_context
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Permission validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Permission validation failed"
            )


class RequirePermission:
    """
    Require specific permission for endpoint access
    Direct permission checking without role hierarchy
    """
    
    def __init__(self, permission_code: str):
        self.permission_code = permission_code
    
    async def __call__(
        self,
        user_context: Dict[str, Any] = Depends(JWTAuth.get_current_user),
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Check if user has specific permission
        """
        try:
            validate_permission = ValidatePermission(db)
            
            has_permission = await validate_permission.check_user_permission(
                user_id=user_context.get("user_id"),
                permission_code=self.permission_code
            )
            
            if not has_permission:
                logger.warning(
                    f"Permission {self.permission_code} denied for user {user_context.get('user_id')}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required permission: {self.permission_code}"
                )
            
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


jwt_auth = JWTAuth()
require_user = RequireUser()

# Dependency exports for easy use in endpoints
GetCurrentUser = Depends(jwt_auth.get_current_user)
AuthenticatedUser = Depends(require_user)

# Permission-based role dependencies (factory functions)
def RequireMaintainer(required_permissions: List[str] = None):
    """Factory function for MAINTAINER role with specific permissions"""
    return Depends(MaintainerOnly(required_permissions))

def RequireAdmin(required_permissions: List[str] = None):
    """Factory function for ADMIN role (or higher) with specific permissions"""
    return Depends(AdminOnly(required_permissions))

def RequireDeptAdmin(required_permissions: List[str] = None):
    """Factory function for DEPT_ADMIN role (or higher) with specific permissions"""
    return Depends(DeptAdminOnly(required_permissions))

def RequireDeptManager(required_permissions: List[str] = None):
    """Factory function for DEPT_MANAGER role (or higher) with specific permissions"""
    return Depends(DeptManagerOnly(required_permissions))