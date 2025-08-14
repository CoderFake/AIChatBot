"""
Authentication Middleware for FastAPI
JWT-based authentication with role verification for Depends()
Integrates AuthService for authentication and ValidatePermission for authorization
"""
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_db
from config.settings import get_settings
from common.types import UserRole
from services.auth.auth_service import AuthService
from services.auth.validate_permission import ValidatePermission
from utils.logging import get_logger

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
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Get current user from JWT token with comprehensive validation:
        1. Decode JWT token
        2. Check token blacklist via AuthService
        3. Validate user status via AuthService
        """
        try:
            token = credentials.credentials
            payload = JWTAuth.decode_token(token)
            
            user_id = payload.get("user_id")
            jti = payload.get("jti")  
            role = payload.get("role")
            tenant_id = payload.get("tenant_id")
            department_id = payload.get("department_id")
            
            if not user_id or not role or not jti:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload - missing required fields"
                )
            
            # Use AuthService for comprehensive token validation
            auth_service = AuthService(db)
            
            # Check token blacklist and user status
            token_validation = await auth_service.validate_token(jti, user_id)
            
            if not token_validation.get("valid"):
                reason = token_validation.get("reason", "token_invalid")
                message = token_validation.get("message", "Token validation failed")
                
                logger.warning(f"Token validation failed for user {user_id}: {reason}")
                
                # Map different failure reasons to appropriate HTTP status
                if reason == "token_blacklisted":
                    status_code = status.HTTP_401_UNAUTHORIZED
                    detail = "Token has been revoked"
                elif reason in ["user_deleted", "user_inactive"]:
                    status_code = status.HTTP_403_FORBIDDEN
                    detail = message
                else:
                    status_code = status.HTTP_401_UNAUTHORIZED
                    detail = "Authentication failed"
                
                raise HTTPException(status_code=status_code, detail=detail)
            
            user_context = {
                "user_id": user_id,
                "jti": jti,
                "role": role,
                "tenant_id": tenant_id,
                "department_id": department_id,
                "email": payload.get("email"),
                "username": payload.get("username"),
                "token_validated": True,
                "validation_timestamp": payload.get("iat"),
                "expires_at": payload.get("exp")
            }
            
            logger.debug(f"Authentication successful: user {user_id} with role {role}")
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
    Uses AuthService for authentication and ValidatePermission for authorization
    """
    def __init__(self, required_permissions: List[str] = None):
        self.required_permissions = required_permissions or []
    
    async def __call__(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        # Step 1: Authentication via JWTAuth (includes token blacklist + user status check)
        user_context = await JWTAuth.get_current_user(credentials, db)
        
        user_role = user_context.get("role")
        
        # Step 2: Role hierarchy check - MAINTAINER can also access ADMIN endpoints
        allowed_roles = [UserRole.ADMIN.value, UserRole.MAINTAINER.value]
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ADMIN role or higher required"
            )
        
        # Step 3: Specific permissions check if provided
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
            
            user_context.update({
                "validated_permissions": validation_result.get("user_permissions", []),
                "permission_validation": validation_result,
                "endpoint_validated": f"{self.http_method} {self.endpoint_path}"
            })
            
            logger.info(
                f"Complete validation passed for user {user_context.get('user_id')} "
                f"on {self.http_method} {self.endpoint_path}"
            )
            
            return user_context
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"API permission validation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Permission validation failed"
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
            validate_permission = ValidatePermission(db)
            
            result = await validate_permission.check_user_has_permissions(
                user_id=user_context.get("user_id"),
                required_permissions=[self.permission_code],
                user_role=user_context.get("role"),
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


jwt_auth = JWTAuth()
require_user = RequireUser()

GetCurrentUser = Depends(jwt_auth.get_current_user)
AuthenticatedUser = Depends(require_user)

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