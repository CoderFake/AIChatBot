from fastapi import APIRouter
from .endpoints import health, documents, tools, config, auth

api_router = APIRouter()

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health"]
)

api_router.include_router(auth.router)