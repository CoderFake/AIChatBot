"""
Auth Middleware cho config management
Xác minh user_id và OTP cho các thao tác config
"""
from typing import Optional, Dict, Any
from fastapi import HTTPException, Header, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.auth.permission_service import PermissionService
from utils.otp import otp_manager
from common.types import UserRole, Department
from utils.logging import get_logger

logger = get_logger(__name__)


class ConfigAuthMiddleware:
    """Middleware cho config management authentication"""
    
    def __init__(self):
        pass
    
    async def verify_config_access(
        self,
        user_id: str = Header(..., alias="X-User-ID"),
        otp_token: str = Header(..., alias="X-OTP-Token"),
        db: AsyncSession = Depends(get_db)
    ) -> Dict[str, Any]:
        """
        Verify user có quyền config và OTP hợp lệ
        
        Args:
            user_id: User ID từ header
            otp_token: OTP token từ header
            db: Database session
            
        Returns:
            Dict chứa user context và permissions
        """
        try:
            # Verify OTP first
            if not otp_manager.verify_totp(otp_token):
                logger.warning(f"Invalid OTP for user {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid OTP token"
                )
            
            # Get user permissions
            permission_service = PermissionService(db)
            user_context = await permission_service.get_user_all_permissions(user_id)
            
            if not user_context:
                logger.warning(f"User {user_id} not found or inactive")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found or inactive"
                )
            
            # Check config permissions
            permissions = user_context.get('permissions', [])
            role = user_context.get('role', '')
            department = user_context.get('department', '')
            
            # Admin có full access
            if role == UserRole.ADMIN.value or 'admin_full_access' in permissions:
                user_context['config_permissions'] = {
                    'can_manage_all_tools': True,
                    'can_manage_all_providers': True,
                    'can_manage_all_configs': True,
                    'departments_allowed': ['all']
                }
            else:
                # Department-specific permissions
                config_perms = {
                    'can_manage_all_tools': False,
                    'can_manage_all_providers': False,
                    'can_manage_all_configs': False,
                    'departments_allowed': [department] if department else []
                }
                
                # Check department config permissions
                if 'config_tools' in permissions:
                    config_perms['can_manage_department_tools'] = True
                
                if 'config_providers' in permissions:
                    config_perms['can_manage_department_providers'] = True
                
                # Manager+ có quyền config department của mình
                if role in [UserRole.MANAGER.value, UserRole.DIRECTOR.value, UserRole.CEO.value]:
                    config_perms['can_manage_department_tools'] = True
                    config_perms['can_manage_department_providers'] = True
                
                user_context['config_permissions'] = config_perms
            
            logger.info(f"Config access verified for user {user_id} with role {role}")
            return user_context
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Config auth verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Authentication verification failed: {str(e)}"
            )
    
    async def verify_tool_config_access(
        self,
        tool_name: str,
        user_context: Dict[str, Any]
    ) -> bool:
        """
        Verify user có quyền config specific tool
        
        Args:
            tool_name: Tên tool cần config
            user_context: User context từ verify_config_access
            
        Returns:
            bool: True nếu có quyền
        """
        config_perms = user_context.get('config_permissions', {})
        department = user_context.get('department', '')
        
        # Admin có full access
        if config_perms.get('can_manage_all_tools'):
            return True
        
        # Check department-specific tools
        if config_perms.get('can_manage_department_tools'):
            # TODO: Check if tool belongs to user's department
            # Có thể check từ tool registry hoặc database
            return True
        
        return False
    
    async def verify_provider_config_access(
        self,
        provider_name: str,
        user_context: Dict[str, Any]
    ) -> bool:
        """
        Verify user có quyền config specific provider
        
        Args:
            provider_name: Tên provider cần config
            user_context: User context từ verify_config_access
            
        Returns:
            bool: True nếu có quyền
        """
        config_perms = user_context.get('config_permissions', {})
        
        # Admin có full access
        if config_perms.get('can_manage_all_providers'):
            return True
        
        # Department managers có thể config providers của department
        if config_perms.get('can_manage_department_providers'):
            return True
        
        return False


config_auth = ConfigAuthMiddleware()


async def verify_config_permission(
    user_id: str = Header(..., alias="X-User-ID"),
    otp_token: str = Header(..., alias="X-OTP-Token"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Dependency function để verify config permissions
    Sử dụng trong các config endpoints
    """
    return await config_auth.verify_config_access(user_id, otp_token, db)


async def verify_admin_permission(
    user_id: str = Header(..., alias="X-User-ID"),
    otp_token: str = Header(..., alias="X-OTP-Token"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Dependency function chỉ cho admin full access
    """
    user_context = await config_auth.verify_config_access(user_id, otp_token, db)
    
    config_perms = user_context.get('config_permissions', {})
    if not config_perms.get('can_manage_all_configs'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    return user_context
