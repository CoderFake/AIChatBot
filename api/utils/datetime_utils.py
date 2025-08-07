from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from config.settings import get_settings

settings = get_settings()

class CustomDateTime(datetime):
    """
    DateTime class with tenant timezone support
    """
    
    default_tz = ZoneInfo(settings.TIMEZONE)
    current_tenant_tz = None
    
    @classmethod
    def set_tenant_timezone(cls, tenant_timezone: str):
        """Set timezone for current tenant"""
        try:
            cls.current_tenant_tz = ZoneInfo(tenant_timezone)
        except Exception:
            cls.current_tenant_tz = cls.default_tz
    
    @classmethod
    def get_active_timezone(cls) -> ZoneInfo:
        """Get currently active timezone"""
        return cls.current_tenant_tz if cls.current_tenant_tz else cls.default_tz

    @classmethod
    def now(cls, tenant_timezone: Optional[str] = None) -> datetime:
        """Get current datetime in tenant timezone"""
        if tenant_timezone:
            tz = ZoneInfo(tenant_timezone)
        else:
            tz = cls.get_active_timezone()
            
        dt_with_tz = super().now(tz)
        return dt_with_tz.astimezone(tz)

    @classmethod
    def fromtimestamp(cls, timestamp: float, tenant_timezone: Optional[str] = None) -> datetime:
        """Create datetime from timestamp in tenant timezone"""
        if tenant_timezone:
            tz = ZoneInfo(tenant_timezone)
        else:
            tz = cls.get_active_timezone()
            
        dt_with_tz = super().fromtimestamp(timestamp, tz)
        return dt_with_tz.astimezone(tz)

    @classmethod
    def fromisoformat(cls, date_string: str, tenant_timezone: Optional[str] = None) -> datetime:
        """Parse ISO format string in tenant timezone"""
        dt = super().fromisoformat(date_string)
        
        if tenant_timezone:
            tz = ZoneInfo(tenant_timezone)
        else:
            tz = cls.get_active_timezone()
        
        if dt.tzinfo is None:
            return dt.replace(tzinfo=tz)
        else:
            return dt.astimezone(tz)

    def to_tenant_timezone(self, tenant_timezone: str) -> datetime:
        """Convert to specific tenant timezone"""
        target_tz = ZoneInfo(tenant_timezone)
        return self.astimezone(target_tz)
    
    def to_localtime(self) -> datetime:
        """Convert to tenant local time"""
        return self.astimezone(self.get_active_timezone())
    
    @classmethod
    def utc_now(cls) -> datetime:
        """Get current UTC time"""
        return super().now(ZoneInfo("UTC"))
    
    def to_utc(self) -> datetime:
        """Convert to UTC"""
        return self.astimezone(ZoneInfo("UTC"))