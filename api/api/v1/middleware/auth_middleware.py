
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
        Verify user has permission to config and OTP is valid
        
        Args:
            user_id: User ID from header
            otp_token: OTP token từ header
            db: Database session
            
        Returns:
            Dict contains user context and permissions   
        """
        try:
            if not otp_manager.verify_totp(otp_token):
                logger.warning(f"Invalid OTP for user {user_id}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid OTP token"
                )
            
            permission_service = PermissionService(db)
            user_context = await permission_service.get_user_all_permissions(user_id)
            
            if not user_context:
                logger.warning(f"User {user_id} not found or inactive")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found or inactive"
                )
            
            config_perms = await permission_service.get_user_config_permissions(user_id)
            user_context['config_permissions'] = config_perms
            
            logger.info(f"Config access verified for user {user_id} with role {user_context.get('role', '')}")
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
        
        if config_perms.get('can_manage_all_tools'):
            return True
      
        if config_perms.get('can_manage_department_tools'):
           
            return True
        
        return False
    
    async def verify_provider_config_access(
        self,
        provider_name: str,
        user_context: Dict[str, Any]
    ) -> bool:
        """
        Verify user has permission to config specific provider
        
        Args:
            provider_name: Name of provider to config
            user_context: User context from verify_config_access
            
        Returns:
            bool: True if has permission
        """ 
        config_perms = user_context.get('config_permissions', {})
        
        if config_perms.get('can_manage_all_providers'):
            return True
        
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
    Dependency function to verify config permissions
    Used in config endpoints
    """
    return await config_auth.verify_config_access(user_id, otp_token, db)


async def verify_admin_permission(
    user_id: str = Header(..., alias="X-User-ID"),
    otp_token: str = Header(..., alias="X-OTP-Token"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Dependency function only for admin full access 
    """
    user_context = await config_auth.verify_config_access(user_id, otp_token, db)
    
    config_perms = user_context.get('config_permissions', {})
    if not config_perms.get('can_manage_all_configs'):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    return user_context
