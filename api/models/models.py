from pydantic import BaseModel, Field
from typing import List, Optional

class RAGSearchInput(BaseModel):
    """Input schema for RAG search tool"""
    query: str = Field(description="Search query for document retrieval")
    department: str = Field(description="User's department for access control")
    user_id: str = Field(description="User ID for permission checking")
    access_levels: List[str] = Field(
        default=["public"],
        description="Access levels for search (public, private, etc.)"
    )
    access_scope_override: Optional[str] = Field(
        default=None,
        description="Explicit access scope override: 'public', 'private', or 'both'"
    )
    user_role: Optional[str] = Field(
        default=None,
        description="Role of the requesting user for cross-department checks"
    )


class CalculatorInput(BaseModel):
    """Input schema for calculator tool"""
    expression: str = Field(
        description="Mathematical expression to evaluate. Supports basic arithmetic operations (+, -, *, /, **), "
                   "parentheses, and common mathematical functions like sqrt, sin, cos, tan, log, etc."
    )



class DateTimeInput(BaseModel):
    """Input schema for datetime tool"""
    operation: str = Field(
        description="Operation to perform: 'current_time', 'current_date', 'current_datetime', "
                   "'format_datetime', 'add_time', 'subtract_time', 'convert_timezone', "
                   "'time_difference', 'parse_datetime', 'timestamp_to_datetime', 'datetime_to_timestamp'"
    )
    timezone: Optional[str] = Field(
        default="UTC",
        description="Timezone for the operation (e.g., 'UTC', 'US/Eastern', 'Asia/Tokyo')"
    )
    datetime_string: Optional[str] = Field(
        default=None,
        description="DateTime string for parsing or formatting operations"
    )
    format_string: Optional[str] = Field(
        default="%Y-%m-%d %H:%M:%S",
        description="Format string for datetime formatting"
    )
    amount: Optional[int] = Field(
        default=None,
        description="Amount to add/subtract (number)"
    )
    unit: Optional[str] = Field(
        default="days",
        description="Unit for add/subtract operations: 'days', 'hours', 'minutes', 'seconds', 'weeks', 'months', 'years'"
    )
    target_timezone: Optional[str] = Field(
        default=None,
        description="Target timezone for conversion operations"
    )
    second_datetime: Optional[str] = Field(
        default=None,
        description="Second datetime for difference calculations"
    )


class WeatherInput(BaseModel):
    """Input schema for weather tool"""
    location: str = Field(
        description="Location to get weather for. Can be city name, coordinates (lat,lon), or airport code."
    )
    units: Optional[str] = Field(
        default="metric",
        description="Temperature units: 'metric' for Celsius, 'imperial' for Fahrenheit, 'kelvin' for Kelvin"
    )
    forecast_days: Optional[int] = Field(
        default=0,
        description="Number of forecast days (0 for current weather only, max 5 for free tier)"
    )



class WebSearchInput(BaseModel):
    """Input schema for web search tool"""
    query: str = Field(
        description="Search query to find information on the web"
    )
    num_results: Optional[int] = Field(
        default=5,
        description="Number of search results to return (1-10)"
    )
    search_engine: Optional[str] = Field(
        default="duckduckgo",
        description="Search engine to use: 'duckduckgo', 'google', 'bing'"
    )
    region: Optional[str] = Field(
        default="wt-wt",
        description="Region code for search (e.g., 'us-en', 'uk-en', 'wt-wt' for worldwide)"
    )
    time_range: Optional[str] = Field(
        default=None,
        description="Time range for results: 'd' (day), 'w' (week), 'm' (month), 'y' (year)"
    )


class SummaryInput(BaseModel):
    """Input schema for summary tool"""
    text: str = Field(
        description="Text content to summarize"
    )
    summary_type: Optional[str] = Field(
        default="concise",
        description="Type of summary: 'concise', 'bullet_points', 'detailed', 'executive', 'key_points'"
    )
    max_length: Optional[int] = Field(
        default=None,
        description="Maximum length of summary in words (optional)"
    )
    focus_areas: Optional[str] = Field(
        default=None,
        description="Specific areas to focus on in the summary (comma-separated)"
    )
    language: Optional[str] = Field(
        default="english",
        description="Language for the summary output"
    )


class LateMinutesInput(BaseModel):
    """Input schema for late minutes tracking tool"""
    users: List[str] = Field(
        description="List of usernames, names, or emails to check late minutes for"
    )
    time_period: str = Field(
        description="Time period to check: 'day', 'week', 'month', 'year'"
    )
    specific_date: Optional[str] = Field(
        default=None,
        description="Specific date in YYYY-MM-DD format (optional, defaults to current period)"
    )
    checkin_time: Optional[str] = Field(
        default=None,
        description="Expected checkin time in HH:MM format (e.g., '09:00')"
    )
    checkout_time: Optional[str] = Field(
        default=None,
        description="Expected checkout time in HH:MM format (e.g., '18:00')"
    )


