from api.api.v1.endpoints import config
from fastapi import APIRouter
from api.v1.endpoints import health, documents, admin
from api.api.v1.endpoints import tools

api_router = APIRouter()

api_router.include_router(
    health.router, 
    prefix="/health", 
    tags=["Health"]
)

api_router.include_router(
    documents.router, 
    prefix="/documents", 
    tags=["Document Management"]
)

api_router.include_router(
    admin.router,
    prefix="/admin",
    tags=["Admin Configuration"]
)

api_router.include_router(
    tools.router,
    prefix="/tools",
    tags=["Tools"]
)