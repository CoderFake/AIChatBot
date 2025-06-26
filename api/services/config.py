"""
Configuration Service
Query database cho user permissions và configurations
"""
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from models.database.user import User
from models.database.permission import Permission, UserPermission, Group, GroupPermission
from models.database.tool import Tool
from common.types import UserRole, Department
from services.auth.permission_service import PermissionService
from utils.logging import get_logger

logger = get_logger(__name__)


class ConfigService:
    """
    Service để query database cho config management
    Xử lý permissions và tool/provider configurations
    """
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.permission_service = PermissionService(db_session)
    
    async def get_user_config_permissions(self, user_id: str) -> Dict[str, Any]:
        """
        Lấy config permissions của user từ database
        
        Args:
            user_id: ID của user
            
        Returns:
            Dict chứa detailed config permissions
        """
        try:
            user_context = await self.permission_service.get_user_all_permissions(user_id)
            
            if not user_context:
                return {}
            
            permissions = user_context.get('permissions', [])
            role = user_context.get('role', '')
            department = user_context.get('department', '')
            
            # Determine config permissions
            config_perms = {
                'user_id': user_id,
                'role': role,
                'department': department,
                'can_manage_all_tools': False,
                'can_manage_all_providers': False,
                'can_manage_all_configs': False,
                'can_manage_department_tools': False,
                'can_manage_department_providers': False,
                'allowed_tools': [],
                'allowed_providers': [],
                'restrictions': {}
            }
            
            # Admin has full access
            if role == UserRole.ADMIN.value or 'admin_full_access' in permissions:
                config_perms.update({
                    'can_manage_all_tools': True,
                    'can_manage_all_providers': True,
                    'can_manage_all_configs': True
                })
                
                # Get all tools and providers for admin
                config_perms['allowed_tools'] = await self._get_all_tools()
                config_perms['allowed_providers'] = await self._get_all_providers()
                
            else:
                # Department-specific permissions
                if 'config_tools' in permissions:
                    config_perms['can_manage_department_tools'] = True
                    config_perms['allowed_tools'] = await self._get_department_tools(department)
                
                if 'config_providers' in permissions:
                    config_perms['can_manage_department_providers'] = True
                    config_perms['allowed_providers'] = await self._get_department_providers(department)
                
                # Manager+ có extended permissions
                if role in [UserRole.MANAGER.value, UserRole.DIRECTOR.value, UserRole.CEO.value]:
                    config_perms['can_manage_department_tools'] = True
                    config_perms['can_manage_department_providers'] = True
                    
                    if not config_perms['allowed_tools']:
                        config_perms['allowed_tools'] = await self._get_department_tools(department)
                    if not config_perms['allowed_providers']:
                        config_perms['allowed_providers'] = await self._get_department_providers(department)
                
                # Set restrictions for non-admin users
                config_perms['restrictions'] = {
                    'department_only': True,
                    'requires_approval': role not in [UserRole.MANAGER.value, UserRole.DIRECTOR.value, UserRole.CEO.value],
                    'max_daily_changes': 10 if role == UserRole.EMPLOYEE.value else 50
                }
            
            return config_perms
            
        except Exception as e:
            logger.error(f"Failed to get user config permissions: {e}")
            return {}
    
    async def verify_tool_config_access(
        self, 
        user_id: str, 
        tool_name: str
    ) -> Dict[str, Any]:
        """
        Verify user có quyền config specific tool
        
        Args:
            user_id: ID của user
            tool_name: Tên tool
            
        Returns:
            Dict chứa access status và metadata
        """
        try:
            config_perms = await self.get_user_config_permissions(user_id)
            
            if not config_perms:
                return {
                    'has_access': False,
                    'reason': 'User not found or no permissions'
                }
            
            # Admin has access to all tools
            if config_perms.get('can_manage_all_tools'):
                return {
                    'has_access': True,
                    'reason': 'Admin privileges',
                    'tool_details': await self._get_tool_details(tool_name)
                }
            
            # Check department tools
            if config_perms.get('can_manage_department_tools'):
                allowed_tools = config_perms.get('allowed_tools', [])
                
                if tool_name in [tool['name'] for tool in allowed_tools]:
                    return {
                        'has_access': True,
                        'reason': 'Department tool access',
                        'tool_details': await self._get_tool_details(tool_name),
                        'restrictions': config_perms.get('restrictions', {})
                    }
            
            return {
                'has_access': False,
                'reason': f'No permission to configure tool {tool_name}',
                'available_tools': [tool['name'] for tool in config_perms.get('allowed_tools', [])]
            }
            
        except Exception as e:
            logger.error(f"Failed to verify tool config access: {e}")
            return {
                'has_access': False,
                'reason': f'Error verifying access: {str(e)}'
            }
    
    async def verify_provider_config_access(
        self, 
        user_id: str, 
        provider_name: str
    ) -> Dict[str, Any]:
        """
        Verify user có quyền config specific provider
        
        Args:
            user_id: ID của user
            provider_name: Tên provider
            
        Returns:
            Dict chứa access status và metadata
        """
        try:
            config_perms = await self.get_user_config_permissions(user_id)
            
            if not config_perms:
                return {
                    'has_access': False,
                    'reason': 'User not found or no permissions'
                }
            
            # Admin has access to all providers
            if config_perms.get('can_manage_all_providers'):
                return {
                    'has_access': True,
                    'reason': 'Admin privileges',
                    'provider_details': await self._get_provider_details(provider_name)
                }
            
            # Check department providers
            if config_perms.get('can_manage_department_providers'):
                allowed_providers = config_perms.get('allowed_providers', [])
                
                if provider_name in allowed_providers:
                    return {
                        'has_access': True,
                        'reason': 'Department provider access',
                        'provider_details': await self._get_provider_details(provider_name),
                        'restrictions': config_perms.get('restrictions', {})
                    }
            
            return {
                'has_access': False,
                'reason': f'No permission to configure provider {provider_name}',
                'available_providers': config_perms.get('allowed_providers', [])
            }
            
        except Exception as e:
            logger.error(f"Failed to verify provider config access: {e}")
            return {
                'has_access': False,
                'reason': f'Error verifying access: {str(e)}'
            }
    
    async def get_department_config_summary(self, department: str) -> Dict[str, Any]:
        """
        Lấy tóm tắt config cho department
        
        Args:
            department: Tên department
            
        Returns:
            Dict chứa config summary
        """
        try:
            summary = {
                'department': department,
                'available_tools': await self._get_department_tools(department),
                'available_providers': await self._get_department_providers(department),
                'total_users': await self._get_department_user_count(department),
                'managers': await self._get_department_managers(department)
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get department config summary: {e}")
            return {}
    
    # Private helper methods
    
    async def _get_all_tools(self) -> List[Dict[str, Any]]:
        """Lấy tất cả tools từ database"""
        try:
            query = select(Tool).where(Tool.is_enabled == True)
            result = await self.db.execute(query)
            tools = result.scalars().all()
            
            return [
                {
                    'id': str(tool.id),
                    'name': tool.name,
                    'display_name': tool.display_name,
                    'category': tool.category,
                    'is_system': tool.is_system,
                    'departments_allowed': tool.departments_allowed
                }
                for tool in tools
            ]
            
        except Exception as e:
            logger.error(f"Failed to get all tools: {e}")
            return []
    
    async def _get_all_providers(self) -> List[str]:
        return ['gemini', 'ollama', 'mistral', 'meta', 'anthropic']
    
    async def _get_department_tools(self, department: str) -> List[Dict[str, Any]]:
        """Lấy tools available cho department"""
        try:
            all_tools = await self._get_all_tools()
            department_tools = []
            
            for tool in all_tools:
                departments_allowed = tool.get('departments_allowed')
                
                # If no department restriction or department is allowed
                if not departments_allowed or department.upper() in [d.upper() for d in departments_allowed]:
                    department_tools.append(tool)
            
            return department_tools
            
        except Exception as e:
            logger.error(f"Failed to get department tools: {e}")
            return []
    
    async def _get_department_providers(self, department: str) -> List[str]:
        """Lấy providers available cho department"""
        # All departments có thể sử dụng all providers
        # TODO: Implement department-specific provider restrictions nếu cần
        return await self._get_all_providers()
    
    async def _get_tool_details(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Lấy detailed info của tool"""
        try:
            query = select(Tool).where(Tool.name == tool_name)
            result = await self.db.execute(query)
            tool = result.scalar_one_or_none()
            
            if not tool:
                return None
            
            return {
                'id': str(tool.id),
                'name': tool.name,
                'display_name': tool.display_name,
                'description': tool.description,
                'category': tool.category,
                'version': tool.version,
                'is_enabled': tool.is_enabled,
                'is_system': tool.is_system,
                'tool_config': tool.tool_config,
                'usage_limits': tool.usage_limits,
                'departments_allowed': tool.departments_allowed,
                'requirements': tool.requirements
            }
            
        except Exception as e:
            logger.error(f"Failed to get tool details: {e}")
            return None
    
    async def _get_provider_details(self, provider_name: str) -> Dict[str, Any]:
        """Lấy detailed info của provider"""
        # Provider details từ settings/config
        # TODO: Implement provider table nếu cần store trong database
        return {
            'name': provider_name,
            'type': 'llm_provider',
            'status': 'available'
        }
    
    async def _get_department_user_count(self, department: str) -> int:
        """Đếm số users trong department"""
        try:
            query = select(User).where(
                and_(
                    User.department == department,
                    User.is_active == True
                )
            )
            result = await self.db.execute(query)
            users = result.scalars().all()
            
            return len(users)
            
        except Exception as e:
            logger.error(f"Failed to get department user count: {e}")
            return 0
    
    async def _get_department_managers(self, department: str) -> List[Dict[str, Any]]:
        """Lấy managers của department"""
        try:
            query = select(User).where(
                and_(
                    User.department == department,
                    User.role.in_([UserRole.MANAGER.value, UserRole.DIRECTOR.value]),
                    User.is_active == True
                )
            )
            result = await self.db.execute(query)
            managers = result.scalars().all()
            
            return [
                {
                    'id': str(manager.id),
                    'username': manager.username,
                    'email': manager.email,
                    'role': manager.role
                }
                for manager in managers
            ]
            
        except Exception as e:
            logger.error(f"Failed to get department managers: {e}")
            return []
