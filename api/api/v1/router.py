
from fastapi import APIRouter
from api.v1.endpoints import (
    auth,
    others,
    tenants,
    agents,
    tools,
    providers,
    chat,
    documents,
    departments,
    maintainer,
    health,
    users,
    tenant_admin,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(tenants.router, prefix="/tenants", tags=["Tenants"])
api_router.include_router(tenant_admin.router, prefix="/tenant-admin", tags=["Tenant Admin"])
api_router.include_router(agents.router, prefix="/agents", tags=["Agents"])
api_router.include_router(tools.router, prefix="/tools", tags=["Tools"])
api_router.include_router(providers.router, prefix="/providers", tags=["Providers"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(departments.router, prefix="/departments", tags=["Departments"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(maintainer.router, prefix="/maintainer", tags=["Maintainer"])
api_router.include_router(others.router, prefix="/others", tags=["Others"])
api_router.include_router(health.router, prefix="/health", tags=["Health"])
