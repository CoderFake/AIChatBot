from datetime import datetime
from zoneinfo import ZoneInfo

from config.settings import get_settings

settings = get_settings()

class CustomDateTime(datetime):
    try:
        tz = ZoneInfo(settings.TIMEZONE)
    except Exception:
        tz = ZoneInfo("Asia/Ho_Chi_Minh")

    @classmethod
    def set_timezone(cls, tz_name: str):
        cls.tz = ZoneInfo(tz_name)

    @classmethod
    def now(cls) -> datetime:
        dt_with_tz = super().now(cls.tz)
        return dt_with_tz.astimezone(cls.tz)

    @classmethod
    def fromtimestamp(cls, timestamp: float) -> datetime:
        dt_with_tz = super().fromtimestamp(timestamp, cls.tz)
        return dt_with_tz.astimezone(cls.tz)

    @classmethod
    def fromisoformat(cls, date_string: str) -> datetime:
        dt = super().fromisoformat(date_string)

        return dt.replace(tzinfo=cls.tz).astimezone(cls.tz)

    def to_localtime(self) -> datetime:
        return self.astimezone(self.tz)