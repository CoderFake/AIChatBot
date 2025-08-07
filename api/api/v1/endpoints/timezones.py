from fastapi import APIRouter, HTTPException

from models.schemas.responses.timezone import (
    TimezoneListResponse,
    TimezoneGroup,
    TimezoneInfo
)

from common.timezones import TimezoneGroups
from utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

@router.get("/", response_model=TimezoneListResponse)
async def get_timezones():
    """
    Get all supported timezones grouped by region
    Used by frontend for tenant timezone selection
    """
    try:
        timezone_data = TimezoneGroups.get_timezone_groups()
        
        groups = []
        total_count = 0
        
        for region_name, timezones in timezone_data.items():
            timezone_infos = [
                TimezoneInfo(
                    value=tz["value"],
                    label=tz["label"],
                    country=tz["country"]
                )
                for tz in timezones
            ]
            
            groups.append(TimezoneGroup(
                region=region_name,
                timezones=timezone_infos
            ))
            
            total_count += len(timezones)
        
        return TimezoneListResponse(
            groups=groups,
            total_timezones=total_count
        )
        
    except Exception as e:
        logger.error(f"Failed to get timezones: {e}")
        raise HTTPException(status_code=500, detail="Failed to get timezones")