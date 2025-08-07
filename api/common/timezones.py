from enum import Enum
from typing import Dict, List


class TimezoneRegion(Enum):
    """Supported timezone regions with commonly used timezones"""
    
    # Asia Pacific
    ASIA_HO_CHI_MINH = "Asia/Ho_Chi_Minh"
    ASIA_BANGKOK = "Asia/Bangkok" 
    ASIA_JAKARTA = "Asia/Jakarta"
    ASIA_SINGAPORE = "Asia/Singapore"
    ASIA_KUALA_LUMPUR = "Asia/Kuala_Lumpur"
    ASIA_MANILA = "Asia/Manila"
    ASIA_TOKYO = "Asia/Tokyo"
    ASIA_SEOUL = "Asia/Seoul"
    ASIA_HONG_KONG = "Asia/Hong_Kong"
    ASIA_SHANGHAI = "Asia/Shanghai"
    ASIA_TAIPEI = "Asia/Taipei"
    ASIA_KOLKATA = "Asia/Kolkata"
    ASIA_DUBAI = "Asia/Dubai"
    
    # Americas
    US_EASTERN = "America/New_York"
    US_CENTRAL = "America/Chicago"
    US_MOUNTAIN = "America/Denver"
    US_PACIFIC = "America/Los_Angeles"
    US_ALASKA = "America/Anchorage"
    US_HAWAII = "Pacific/Honolulu"
    AMERICA_SAO_PAULO = "America/Sao_Paulo"
    AMERICA_ARGENTINA = "America/Argentina/Buenos_Aires"
    AMERICA_MEXICO = "America/Mexico_City"
    CANADA_EASTERN = "America/Toronto"
    CANADA_PACIFIC = "America/Vancouver"
    
    # Europe
    EUROPE_LONDON = "Europe/London"
    EUROPE_PARIS = "Europe/Paris"
    EUROPE_BERLIN = "Europe/Berlin"
    EUROPE_ROME = "Europe/Rome"
    EUROPE_MADRID = "Europe/Madrid"
    EUROPE_AMSTERDAM = "Europe/Amsterdam"
    EUROPE_STOCKHOLM = "Europe/Stockholm"
    EUROPE_MOSCOW = "Europe/Moscow"
    EUROPE_ISTANBUL = "Europe/Istanbul"
    
    # Africa & Middle East
    AFRICA_CAIRO = "Africa/Cairo"
    AFRICA_JOHANNESBURG = "Africa/Johannesburg"
    AFRICA_LAGOS = "Africa/Lagos"
    AFRICA_CASABLANCA = "Africa/Casablanca"
    
    # Australia & Oceania
    AUSTRALIA_SYDNEY = "Australia/Sydney"
    AUSTRALIA_MELBOURNE = "Australia/Melbourne"
    AUSTRALIA_PERTH = "Australia/Perth"
    PACIFIC_AUCKLAND = "Pacific/Auckland"
    
    # UTC
    UTC = "UTC"


class TimezoneGroups:
    """Grouped timezones by region for better UX"""
    
    @staticmethod
    def get_timezone_groups() -> Dict[str, List[Dict[str, str]]]:
        """Get timezones grouped by regions"""
        return {
            "Asia Pacific": [
                {"value": TimezoneRegion.ASIA_HO_CHI_MINH.value, "label": "Ho Chi Minh City (GMT+7)", "country": "Vietnam"},
                {"value": TimezoneRegion.ASIA_BANGKOK.value, "label": "Bangkok (GMT+7)", "country": "Thailand"},
                {"value": TimezoneRegion.ASIA_JAKARTA.value, "label": "Jakarta (GMT+7)", "country": "Indonesia"},
                {"value": TimezoneRegion.ASIA_SINGAPORE.value, "label": "Singapore (GMT+8)", "country": "Singapore"},
                {"value": TimezoneRegion.ASIA_KUALA_LUMPUR.value, "label": "Kuala Lumpur (GMT+8)", "country": "Malaysia"},
                {"value": TimezoneRegion.ASIA_MANILA.value, "label": "Manila (GMT+8)", "country": "Philippines"},
                {"value": TimezoneRegion.ASIA_TOKYO.value, "label": "Tokyo (GMT+9)", "country": "Japan"},
                {"value": TimezoneRegion.ASIA_SEOUL.value, "label": "Seoul (GMT+9)", "country": "South Korea"},
                {"value": TimezoneRegion.ASIA_HONG_KONG.value, "label": "Hong Kong (GMT+8)", "country": "Hong Kong"},
                {"value": TimezoneRegion.ASIA_SHANGHAI.value, "label": "Shanghai (GMT+8)", "country": "China"},
                {"value": TimezoneRegion.ASIA_TAIPEI.value, "label": "Taipei (GMT+8)", "country": "Taiwan"},
                {"value": TimezoneRegion.ASIA_KOLKATA.value, "label": "Kolkata (GMT+5:30)", "country": "India"},
                {"value": TimezoneRegion.ASIA_DUBAI.value, "label": "Dubai (GMT+4)", "country": "UAE"},
            ],
            "North America": [
                {"value": TimezoneRegion.US_EASTERN.value, "label": "Eastern Time (GMT-5/-4)", "country": "USA"},
                {"value": TimezoneRegion.US_CENTRAL.value, "label": "Central Time (GMT-6/-5)", "country": "USA"},
                {"value": TimezoneRegion.US_MOUNTAIN.value, "label": "Mountain Time (GMT-7/-6)", "country": "USA"},
                {"value": TimezoneRegion.US_PACIFIC.value, "label": "Pacific Time (GMT-8/-7)", "country": "USA"},
                {"value": TimezoneRegion.US_ALASKA.value, "label": "Alaska Time (GMT-9/-8)", "country": "USA"},
                {"value": TimezoneRegion.US_HAWAII.value, "label": "Hawaii Time (GMT-10)", "country": "USA"},
                {"value": TimezoneRegion.CANADA_EASTERN.value, "label": "Eastern Time (GMT-5/-4)", "country": "Canada"},
                {"value": TimezoneRegion.CANADA_PACIFIC.value, "label": "Pacific Time (GMT-8/-7)", "country": "Canada"},
                {"value": TimezoneRegion.AMERICA_MEXICO.value, "label": "Mexico City (GMT-6/-5)", "country": "Mexico"},
            ],
            "South America": [
                {"value": TimezoneRegion.AMERICA_SAO_PAULO.value, "label": "São Paulo (GMT-3)", "country": "Brazil"},
                {"value": TimezoneRegion.AMERICA_ARGENTINA.value, "label": "Buenos Aires (GMT-3)", "country": "Argentina"},
            ],
            "Europe": [
                {"value": TimezoneRegion.EUROPE_LONDON.value, "label": "London (GMT+0/+1)", "country": "UK"},
                {"value": TimezoneRegion.EUROPE_PARIS.value, "label": "Paris (GMT+1/+2)", "country": "France"},
                {"value": TimezoneRegion.EUROPE_BERLIN.value, "label": "Berlin (GMT+1/+2)", "country": "Germany"},
                {"value": TimezoneRegion.EUROPE_ROME.value, "label": "Rome (GMT+1/+2)", "country": "Italy"},
                {"value": TimezoneRegion.EUROPE_MADRID.value, "label": "Madrid (GMT+1/+2)", "country": "Spain"},
                {"value": TimezoneRegion.EUROPE_AMSTERDAM.value, "label": "Amsterdam (GMT+1/+2)", "country": "Netherlands"},
                {"value": TimezoneRegion.EUROPE_STOCKHOLM.value, "label": "Stockholm (GMT+1/+2)", "country": "Sweden"},
                {"value": TimezoneRegion.EUROPE_MOSCOW.value, "label": "Moscow (GMT+3)", "country": "Russia"},
                {"value": TimezoneRegion.EUROPE_ISTANBUL.value, "label": "Istanbul (GMT+3)", "country": "Turkey"},
            ],
            "Africa & Middle East": [
                {"value": TimezoneRegion.AFRICA_CAIRO.value, "label": "Cairo (GMT+2)", "country": "Egypt"},
                {"value": TimezoneRegion.AFRICA_JOHANNESBURG.value, "label": "Johannesburg (GMT+2)", "country": "South Africa"},
                {"value": TimezoneRegion.AFRICA_LAGOS.value, "label": "Lagos (GMT+1)", "country": "Nigeria"},
                {"value": TimezoneRegion.AFRICA_CASABLANCA.value, "label": "Casablanca (GMT+0/+1)", "country": "Morocco"},
            ],
            "Australia & Oceania": [
                {"value": TimezoneRegion.AUSTRALIA_SYDNEY.value, "label": "Sydney (GMT+10/+11)", "country": "Australia"},
                {"value": TimezoneRegion.AUSTRALIA_MELBOURNE.value, "label": "Melbourne (GMT+10/+11)", "country": "Australia"},
                {"value": TimezoneRegion.AUSTRALIA_PERTH.value, "label": "Perth (GMT+8)", "country": "Australia"},
                {"value": TimezoneRegion.PACIFIC_AUCKLAND.value, "label": "Auckland (GMT+12/+13)", "country": "New Zealand"},
            ],
            "UTC": [
                {"value": TimezoneRegion.UTC.value, "label": "Coordinated Universal Time", "country": "UTC"},
            ]
        }
    
    @staticmethod
    def get_all_timezones() -> List[str]:
        """Get all supported timezone values"""
        return [tz.value for tz in TimezoneRegion]
    
    @staticmethod
    def is_valid_timezone(timezone: str) -> bool:
        """Validate if timezone is supported"""
        return timezone in TimezoneGroups.get_all_timezones()
    
    @staticmethod
    def get_timezone_info(timezone: str) -> Dict[str, str]:
        """Get information about specific timezone"""
        all_groups = TimezoneGroups.get_timezone_groups()
        
        for group_name, timezones in all_groups.items():
            for tz_info in timezones:
                if tz_info["value"] == timezone:
                    return {
                        "timezone": timezone,
                        "group": group_name,
                        "label": tz_info["label"],
                        "country": tz_info["country"]
                    }
        
        return {
            "timezone": timezone,
            "group": "Unknown",
            "label": timezone,
            "country": "Unknown"
        }

