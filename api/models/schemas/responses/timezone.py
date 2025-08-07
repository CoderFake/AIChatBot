from typing import List, Dict
from pydantic import BaseModel


class TimezoneInfo(BaseModel):
    """Single timezone information"""
    value: str
    label: str
    country: str


class TimezoneGroup(BaseModel):
    """Timezone group by region"""
    region: str
    timezones: List[TimezoneInfo]


class TimezoneListResponse(BaseModel):
    """Response model for timezone list"""
    groups: List[TimezoneGroup]
    total_timezones: int