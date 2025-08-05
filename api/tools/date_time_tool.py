"""
Date Time Tool implementation
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, Type
from langchain_core.tools import BaseTool
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from pydantic import BaseModel
import pytz
from api.models.models import DateTimeInput
from utils.logging import get_logger


logger = get_logger(__name__)


class DateTimeTool(BaseTool):
    """
    DateTime tool for date and time operations
    Supports various datetime operations including formatting, timezone conversion, arithmetic, etc.
    """
    name = "datetime"
    description = "Performs date and time operations including getting current time, formatting, timezone conversion, and date arithmetic."
    args_schema: Type[BaseModel] = DateTimeInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("Initialized datetime tool")

    def _get_timezone(self, tz_name: str) -> timezone:
        """Get timezone object from string"""
        try:
            if tz_name.upper() == "UTC":
                return timezone.utc
            return pytz.timezone(tz_name)
        except Exception:
            logger.warning(f"Invalid timezone {tz_name}, using UTC")
            return timezone.utc

    def _parse_datetime(self, dt_string: str, format_str: Optional[str] = None) -> datetime:
        """Parse datetime string"""
        if format_str:
            return datetime.strptime(dt_string, format_str)
        
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S.%fZ",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(dt_string, fmt)
            except ValueError:
                continue
        
        raise ValueError(f"Unable to parse datetime string: {dt_string}")

    def _perform_operation(
        self,
        operation: str,
        timezone_name: str = "UTC",
        datetime_string: Optional[str] = None,
        format_string: str = "%Y-%m-%d %H:%M:%S",
        amount: Optional[int] = None,
        unit: str = "days",
        target_timezone: Optional[str] = None,
        second_datetime: Optional[str] = None,
    ) -> str:
        """Perform the datetime operation"""
        
        try:
            tz = self._get_timezone(timezone_name)
            
            if operation == "current_time":
                now = datetime.now(tz)
                return now.strftime("%H:%M:%S")
            
            elif operation == "current_date":
                now = datetime.now(tz)
                return now.strftime("%Y-%m-%d")
            
            elif operation == "current_datetime":
                now = datetime.now(tz)
                return now.strftime(format_string)
            
            elif operation == "format_datetime":
                if not datetime_string:
                    return "Error: datetime_string is required for format_datetime"
                dt = self._parse_datetime(datetime_string)
                return dt.strftime(format_string)
            
            elif operation == "add_time":
                if not datetime_string or amount is None:
                    return "Error: datetime_string and amount are required for add_time"
                
                dt = self._parse_datetime(datetime_string)
                
                if unit == "days":
                    dt += timedelta(days=amount)
                elif unit == "hours":
                    dt += timedelta(hours=amount)
                elif unit == "minutes":
                    dt += timedelta(minutes=amount)
                elif unit == "seconds":
                    dt += timedelta(seconds=amount)
                elif unit == "weeks":
                    dt += timedelta(weeks=amount)
                else:
                    return f"Error: Invalid unit '{unit}'"
                
                return dt.strftime(format_string)
            
            elif operation == "subtract_time":
                if not datetime_string or amount is None:
                    return "Error: datetime_string and amount are required for subtract_time"
                
                dt = self._parse_datetime(datetime_string)
                
                if unit == "days":
                    dt -= timedelta(days=amount)
                elif unit == "hours":
                    dt -= timedelta(hours=amount)
                elif unit == "minutes":
                    dt -= timedelta(minutes=amount)
                elif unit == "seconds":
                    dt -= timedelta(seconds=amount)
                elif unit == "weeks":
                    dt -= timedelta(weeks=amount)
                else:
                    return f"Error: Invalid unit '{unit}'"
                
                return dt.strftime(format_string)
            
            elif operation == "convert_timezone":
                if not datetime_string or not target_timezone:
                    return "Error: datetime_string and target_timezone are required for convert_timezone"
                
                dt = self._parse_datetime(datetime_string)
                if dt.tzinfo is None:
                    dt = tz.localize(dt)
                
                target_tz = self._get_timezone(target_timezone)
                converted_dt = dt.astimezone(target_tz)
                
                return converted_dt.strftime(format_string)
            
            elif operation == "time_difference":
                if not datetime_string or not second_datetime:
                    return "Error: datetime_string and second_datetime are required for time_difference"
                
                dt1 = self._parse_datetime(datetime_string)
                dt2 = self._parse_datetime(second_datetime)
                
                diff = abs(dt2 - dt1)
                
                days = diff.days
                hours, remainder = divmod(diff.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                
                result = []
                if days > 0:
                    result.append(f"{days} days")
                if hours > 0:
                    result.append(f"{hours} hours")
                if minutes > 0:
                    result.append(f"{minutes} minutes")
                if seconds > 0:
                    result.append(f"{seconds} seconds")
                
                return ", ".join(result) if result else "0 seconds"
            
            elif operation == "parse_datetime":
                if not datetime_string:
                    return "Error: datetime_string is required for parse_datetime"
                
                dt = self._parse_datetime(datetime_string, format_string if format_string != "%Y-%m-%d %H:%M:%S" else None)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            
            elif operation == "timestamp_to_datetime":
                if not datetime_string:
                    return "Error: datetime_string (timestamp) is required for timestamp_to_datetime"
                
                try:
                    timestamp = float(datetime_string)
                    dt = datetime.fromtimestamp(timestamp, tz=tz)
                    return dt.strftime(format_string)
                except ValueError:
                    return f"Error: Invalid timestamp '{datetime_string}'"
            
            elif operation == "datetime_to_timestamp":
                if not datetime_string:
                    return "Error: datetime_string is required for datetime_to_timestamp"
                
                dt = self._parse_datetime(datetime_string)
                return str(int(dt.timestamp()))
            
            else:
                return f"Error: Unknown operation '{operation}'"
                
        except Exception as e:
            logger.error(f"DateTime operation error: {e}")
            return f"Error: {str(e)}"

    def _run(
        self,
        operation: str,
        timezone: str = "UTC",
        datetime_string: Optional[str] = None,
        format_string: str = "%Y-%m-%d %H:%M:%S",
        amount: Optional[int] = None,
        unit: str = "days",
        target_timezone: Optional[str] = None,
        second_datetime: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """
        Execute datetime operation synchronously
        
        Args:
            operation: Type of datetime operation to perform
            timezone: Source timezone
            datetime_string: DateTime string for operations
            format_string: Format string for output
            amount: Amount for add/subtract operations
            unit: Unit for add/subtract operations
            target_timezone: Target timezone for conversion
            second_datetime: Second datetime for difference calculations
            run_manager: Optional callback manager for tool run
            
        Returns:
            String result of the datetime operation
        """
        logger.info(f"Performing datetime operation: {operation}")
        
        result = self._perform_operation(
            operation=operation,
            timezone_name=timezone,
            datetime_string=datetime_string,
            format_string=format_string,
            amount=amount,
            unit=unit,
            target_timezone=target_timezone,
            second_datetime=second_datetime,
        )
        
        logger.info(f"DateTime operation result: {result}")
        return result

    async def _arun(
        self,
        operation: str,
        timezone: str = "UTC",
        datetime_string: Optional[str] = None,
        format_string: str = "%Y-%m-%d %H:%M:%S",
        amount: Optional[int] = None,
        unit: str = "days",
        target_timezone: Optional[str] = None,
        second_datetime: Optional[str] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """
        Execute datetime operation asynchronously
        
        Args:
            operation: Type of datetime operation to perform
            timezone: Source timezone
            datetime_string: DateTime string for operations
            format_string: Format string for output
            amount: Amount for add/subtract operations
            unit: Unit for add/subtract operations
            target_timezone: Target timezone for conversion
            second_datetime: Second datetime for difference calculations
            run_manager: Optional async callback manager for tool run
            
        Returns:
            String result of the datetime operation
        """
        return self._run(
            operation=operation,
            timezone=timezone,
            datetime_string=datetime_string,
            format_string=format_string,
            amount=amount,
            unit=unit,
            target_timezone=target_timezone,
            second_datetime=second_datetime,
            run_manager=None,
        )