from enum import Enum
from common.types import DocumentAccessLevel as CommonDocumentAccessLevel, DBDocumentPermissionLevel as CommonDBDocumentPermissionLevel


class RoleTypes(str, Enum):
    MAINTAINER = "MAINTAINER"
    ADMIN = "ADMIN"
    DEPT_ADMIN = "DEPT_ADMIN"
    DEPT_MANAGER = "DEPT_MANAGER"
    USER = "USER"


DocumentAccessLevel = CommonDocumentAccessLevel
DBDocumentPermissionLevel = CommonDBDocumentPermissionLevel
