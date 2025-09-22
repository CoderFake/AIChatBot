from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Optional

try:
    from sqlalchemy.ext.asyncio import AsyncSession  # type: ignore
    from sqlalchemy import select  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional during tests
    AsyncSession = Any  # type: ignore
    select = None  # type: ignore

from config.settings import get_settings

settings = get_settings()

class DateTimeManager:
    """
    Centralized DateTime management with clear separation:
    - Maintainer operations (tools, providers management) use system timezone
    - Tenant operations (user CRUD, business logic) use tenant timezone with cache fallback
    """
    
    system_tz = ZoneInfo(settings.TIMEZONE)
    
    @classmethod
    def _now(cls) -> datetime:
        """
        Get current datetime in system timezone for maintainer operations.
        Use for: Tool management, Provider management, System maintenance
        """
        return datetime.now(cls.system_tz)

    @classmethod
    def system_now(cls) -> datetime:
        """
        Alias for _now() - for system/maintainer operations.
        Use for: System events, maintenance tasks, config changes
        """
        return cls._now()

    @classmethod
    def maintainer_now(cls) -> datetime:
        """
        Alias for _now() - for maintainer operations.
        Use for: Document processing, batch operations, system tasks
        """
        return cls._now()
    
    @classmethod
    def utc_now(cls) -> datetime:
        """Get current UTC time for database storage and inter-system communication"""
        return datetime.now(ZoneInfo("UTC"))
    
    @classmethod
    def tenant_now(cls, tenant_timezone: str) -> datetime:
        """
        Get current datetime in specific tenant timezone.
        Use for: Tenant CRUD operations, business logic, user-facing features
        """
        try:
            tz = ZoneInfo(tenant_timezone)
            return datetime.now(tz)
        except Exception:
            return cls._now()
    
    @classmethod
    async def get_tenant_timezone(cls, tenant_id: Optional[str], db: Optional[AsyncSession] = None) -> str:
        """Resolve the tenant timezone, falling back to the system default when unavailable."""

        if not tenant_id:
            return settings.TIMEZONE

        return await cls._get_tenant_timezone_cached(tenant_id, db)

    @classmethod
    async def tenant_now_cached(cls, tenant_id: Optional[str], db: Optional[AsyncSession] = None) -> datetime:
        """
        Get current datetime in tenant timezone with cache optimization.
        Order: Redis cache -> DB (with cache backfill) -> system default
        Use for: All tenant-level CRUD operations
        """
        if not tenant_id:
            return cls._now()
        
        tenant_timezone = await cls.get_tenant_timezone(tenant_id, db)
        return cls.tenant_now(tenant_timezone)
    
    @classmethod
    async def _get_tenant_timezone_cached(cls, tenant_id: str, db: Optional[AsyncSession] = None) -> str:
        """
        Get tenant timezone with cache optimization.
        Returns system timezone as fallback.
        """
        try:
            from services.orchestrator.orchestrator import global_cache_manager
            if global_cache_manager is not None:
                cache_key = f"tenant:{tenant_id}:details"
                cached = await global_cache_manager.get(cache_key)
                if cached and isinstance(cached, dict):
                    tz_name = cached.get("timezone")
                    if tz_name:
                        return str(tz_name)
        except Exception:
            pass
        
        if db is not None and select is not None:
            try:
                from models.database.tenant import Tenant
                result = await db.execute(select(Tenant.timezone).where(Tenant.id == tenant_id))
                row = result.first()
                if row and row[0]:
                    tz_name = str(row[0])
                    try:
                        if global_cache_manager is not None:
                            cache_key = f"tenant:{tenant_id}:details"
                            await global_cache_manager.set(cache_key, {"timezone": tz_name})
                    except Exception:
                        pass
                    return tz_name
            except Exception:
                pass
        
        return settings.TIMEZONE
    
    @classmethod
    def convert_to_tenant_tz(cls, dt: datetime, tenant_timezone: str) -> datetime:
        """Convert datetime to tenant timezone"""
        try:
            target_tz = ZoneInfo(tenant_timezone)
            return dt.astimezone(target_tz)
        except Exception:
            return dt.astimezone(cls.system_tz)
    
    @classmethod
    def convert_to_utc(cls, dt: datetime) -> datetime:
        """Convert datetime to UTC"""
        return dt.astimezone(ZoneInfo("UTC"))


# Backward compatibility - gradually deprecate
class CustomDateTime(datetime):
    """
    DEPRECATED: Use DateTimeManager instead.
    Keeping for backward compatibility during migration.
    """
    
    @classmethod
    def now(cls, tenant_timezone: Optional[str] = None) -> datetime:
        """DEPRECATED: Use DateTimeManager._now() or DateTimeManager.tenant_now()"""
        if tenant_timezone:
            return DateTimeManager.tenant_now(tenant_timezone)
        return DateTimeManager._now()
    
    @classmethod
    async def now_for_tenant(cls, tenant_id: Optional[str], db: Optional[AsyncSession] = None) -> datetime:
        """DEPRECATED: Use DateTimeManager.tenant_now_cached()"""
        return await DateTimeManager.tenant_now_cached(tenant_id, db)
    
    @classmethod
    def utc_now(cls) -> datetime:
        """DEPRECATED: Use DateTimeManager.utc_now()"""
        return DateTimeManager.utc_now()