from fastapi import APIRouter
from api.v1.endpoints import health, query, documents, admin

api_router = APIRouter()

# Core API endpoints
api_router.include_router(
    health.router, 
    prefix="/health", 
    tags=["Health"]
)

api_router.include_router(
    query.router, 
    prefix="/query", 
    tags=["RAG Query"]
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