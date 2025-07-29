from typing import Set
from enum import Enum

from common.types import *


ACCESS_PERMISSIONS = {
    AccessLevel.PUBLIC: set(), 
    AccessLevel.PRIVATE: set(),  
    AccessLevel.INTERNAL: {
        UserRole.EMPLOYEE,
        UserRole.MANAGER,
        UserRole.DIRECTOR,
        UserRole.CEO,
        UserRole.ADMIN
    },
    AccessLevel.CONFIDENTIAL: {
        UserRole.MANAGER,
        UserRole.DIRECTOR,
        UserRole.CEO,
        UserRole.ADMIN
    },
    AccessLevel.RESTRICTED: {
        UserRole.DIRECTOR,
        UserRole.CEO,
        UserRole.ADMIN
    }
}


def check_document_access(access_level: str, user_role: str, user_department: str, document_department: str) -> bool:
    """
    Kiểm tra quyền truy cập tài liệu dựa trên cấp độ bảo mật
    
    Args:
        access_level: Cấp độ truy cập của tài liệu
        user_role: Vai trò của người dùng
        user_department: Phòng ban của người dùng
        document_department: Phòng ban sở hữu tài liệu
        
    Returns:
        bool: True nếu có quyền truy cập, False nếu không
    """
    try:
        access_enum = AccessLevel(access_level)
        
        if access_enum == AccessLevel.PUBLIC:
            return True
        
        if access_enum == AccessLevel.PRIVATE:
            return user_department == document_department
        
        try:
            user_role_enum = UserRole(user_role)
            required_roles = ACCESS_PERMISSIONS.get(access_enum, set())
            return user_role_enum in required_roles
        except ValueError:
            return False
            
    except ValueError:
        return False
