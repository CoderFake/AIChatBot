from fastapi import APIRouter
from .endpoints import health, documents, tools, config, auth, tenants, timezones

api_router = APIRouter()

api_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health"]
)

api_router.include_router(auth.router)
api_router.include_router(tenants.router, prefix="/admin")
api_router.include_router(config.router)
api_router.include_router(timezones.router)