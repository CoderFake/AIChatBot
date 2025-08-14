"""
Weather Tool implementation
"""
import json
import requests
from typing import Dict, Any, Optional, Type
from langchain_core.tools import BaseTool
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from pydantic import BaseModel
import aiohttp
import asyncio
from models.models import WeatherInput
from utils.logging import get_logger

logger = get_logger(__name__)


class WeatherTool(BaseTool):
    """
    Weather tool for getting current weather and forecasts
    Uses OpenWeatherMap API (requires API key in environment or config)
    """
    name: str = "weather"
    description: str = "Gets current weather conditions and forecasts for a specified location."
    args_schema: Type[BaseModel] = WeatherInput

    api_key: Optional[str] = None
    base_url: str = "https://api.openweathermap.org/data/2.5"
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        if not api_key:
            import os
            api_key = os.getenv("OPENWEATHERMAP_API_KEY")
        super().__init__(api_key=api_key, **kwargs)
        logger.info("Initialized weather tool")
        
        if not self.api_key:
            logger.warning("No OpenWeatherMap API key found. Weather tool may not work.")

    def _parse_coordinates(self, location: str) -> Optional[tuple]:
        """Parse coordinates from location string"""
        try:
            if ',' in location:
                parts = location.split(',')
                if len(parts) == 2:
                    lat = float(parts[0].strip())
                    lon = float(parts[1].strip())
                    return (lat, lon)
        except ValueError:
            pass
        return None

    def _build_weather_url(self, location: str, units: str, endpoint: str = "weather") -> str:
        """Build API URL for weather request"""
        coords = self._parse_coordinates(location)
        
        if coords:
            lat, lon = coords
            url = f"{self.base_url}/{endpoint}?lat={lat}&lon={lon}&appid={self.api_key}&units={units}"
        else:
            url = f"{self.base_url}/{endpoint}?q={location}&appid={self.api_key}&units={units}"
        
        return url

    def _format_temperature(self, temp: float, units: str) -> str:
        """Format temperature with appropriate unit"""
        if units == "metric":
            return f"{temp:.1f}°C"
        elif units == "imperial":
            return f"{temp:.1f}°F"
        else:  # kelvin
            return f"{temp:.1f}K"

    def _format_current_weather(self, data: dict, units: str) -> str:
        """Format current weather data"""
        try:
            location = data.get("name", "Unknown")
            country = data.get("sys", {}).get("country", "")
            if country:
                location += f", {country}"
            
            main = data.get("main", {})
            weather = data.get("weather", [{}])[0]
            wind = data.get("wind", {})
            
            temp = main.get("temp", 0)
            feels_like = main.get("feels_like", 0)
            humidity = main.get("humidity", 0)
            pressure = main.get("pressure", 0)
            
            description = weather.get("description", "").title()
            wind_speed = wind.get("speed", 0)
            
            if units == "metric":
                wind_unit = "m/s"
            elif units == "imperial":
                wind_unit = "mph"
            else:
                wind_unit = "m/s"
            
            result = f"Current weather in {location}:\n"
            result += f"Temperature: {self._format_temperature(temp, units)}\n"
            result += f"Feels like: {self._format_temperature(feels_like, units)}\n"
            result += f"Condition: {description}\n"
            result += f"Humidity: {humidity}%\n"
            result += f"Pressure: {pressure} hPa\n"
            result += f"Wind speed: {wind_speed} {wind_unit}"
            
            wind_deg = wind.get("deg")
            if wind_deg is not None:
                result += f" ({self._wind_direction(wind_deg)})"
            
            return result
            
        except Exception as e:
            logger.error(f"Error formatting weather data: {e}")
            return "Error: Unable to format weather data"

    def _wind_direction(self, degrees: float) -> str:
        """Convert wind degrees to direction"""
        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                     "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        index = int((degrees + 11.25) / 22.5) % 16
        return directions[index]

    def _format_forecast(self, data: dict, units: str, days: int) -> str:
        """Format forecast data"""
        try:
            city = data.get("city", {}).get("name", "Unknown")
            country = data.get("city", {}).get("country", "")
            if country:
                city += f", {country}"
            
            forecasts = data.get("list", [])
            
            result = f"Weather forecast for {city}:\n\n"
            
            daily_forecasts = {}
            for forecast in forecasts[:days * 8]: 
                date = forecast.get("dt_txt", "").split(" ")[0]
                if date not in daily_forecasts:
                    daily_forecasts[date] = []
                daily_forecasts[date].append(forecast)
            
            for date, day_forecasts in list(daily_forecasts.items())[:days]:
                result += f"📅 {date}:\n"
                
                temps = [f.get("main", {}).get("temp", 0) for f in day_forecasts]
                min_temp = min(temps)
                max_temp = max(temps)
                
                conditions = [f.get("weather", [{}])[0].get("description", "") for f in day_forecasts]
                main_condition = max(set(conditions), key=conditions.count).title()
                
                result += f"  Temperature: {self._format_temperature(min_temp, units)} - {self._format_temperature(max_temp, units)}\n"
                result += f"  Condition: {main_condition}\n"
                
                result += "  Hourly details:\n"
                for forecast in day_forecasts[:4]: 
                    time = forecast.get("dt_txt", "").split(" ")[1][:5]
                    temp = forecast.get("main", {}).get("temp", 0)
                    desc = forecast.get("weather", [{}])[0].get("description", "").title()
                    result += f"    {time}: {self._format_temperature(temp, units)}, {desc}\n"
                
                result += "\n"
            
            return result.strip()
            
        except Exception as e:
            logger.error(f"Error formatting forecast data: {e}")
            return "Error: Unable to format forecast data"

    def _get_weather(self, location: str, units: str, forecast_days: int) -> str:
        """Get weather data from API"""
        if not self.api_key:
            return "Error: OpenWeatherMap API key not configured"
        
        try:
            if forecast_days > 0:
                url = self._build_weather_url(location, units, "forecast")
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    return self._format_forecast(data, units, min(forecast_days, 5))
                elif response.status_code == 401:
                    return "Error: Invalid API key"
                elif response.status_code == 404:
                    return f"Error: Location '{location}' not found"
                else:
                    return f"Error: Weather API returned status {response.status_code}"
                    
        except requests.exceptions.Timeout:
            return "Error: Weather API request timed out"
        except requests.exceptions.RequestException as e:
            logger.error(f"Weather API request error: {e}")
            return "Error: Unable to connect to weather service"
        except Exception as e:
            logger.error(f"Weather tool error: {e}")
            return f"Error: {str(e)}"

    async def _get_weather_async(self, location: str, units: str, forecast_days: int) -> str:
        """Get weather data from API asynchronously"""
        if not self.api_key:
            return "Error: OpenWeatherMap API key not configured"
        
        try:
            async with aiohttp.ClientSession() as session:
                if forecast_days > 0:
                    url = self._build_weather_url(location, units, "forecast")
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            data = await response.json()
                            return self._format_forecast(data, units, min(forecast_days, 5))
                        elif response.status == 401:
                            return "Error: Invalid API key"
                        elif response.status == 404:
                            return f"Error: Location '{location}' not found"
                        else:
                            return f"Error: Weather API returned status {response.status}"
                else:
                    url = self._build_weather_url(location, units, "weather")
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            data = await response.json()
                            return self._format_current_weather(data, units)
                        elif response.status == 401:
                            return "Error: Invalid API key"
                        elif response.status == 404:
                            return f"Error: Location '{location}' not found"
                        else:
                            return f"Error: Weather API returned status {response.status}"
                            
        except asyncio.TimeoutError:
            return "Error: Weather API request timed out"
        except aiohttp.ClientError as e:
            logger.error(f"Weather API async request error: {e}")
            return "Error: Unable to connect to weather service"
        except Exception as e:
            logger.error(f"Weather tool async error: {e}")
            return f"Error: {str(e)}"

    def _run(
        self,
        location: str,
        units: str = "metric",
        forecast_days: int = 0,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """
        Execute weather query synchronously
        
        Args:
            location: Location to get weather for
            units: Temperature units (metric/imperial/kelvin)
            forecast_days: Number of forecast days (0-5)
            run_manager: Optional callback manager for tool run
            
        Returns:
            Formatted weather information
        """
        logger.info(f"Getting weather for location: {location}")
        
        if not location.strip():
            return "Error: Location is required"
        
        result = self._get_weather(location, units, forecast_days)
        logger.info(f"Weather query completed for {location}")
        
        return result

    async def _arun(
        self,
        location: str,
        units: str = "metric",
        forecast_days: int = 0,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """
        Execute weather query asynchronously
        
        Args:
            location: Location to get weather for
            units: Temperature units (metric/imperial/kelvin)
            forecast_days: Number of forecast days (0-5)
            run_manager: Optional async callback manager for tool run
            
        Returns:
            Formatted weather information
        """
        logger.info(f"Getting weather async for location: {location}")
        
        if not location.strip():
            return "Error: Location is required"
        
        result = await self._get_weather_async(location, units, forecast_days)
        logger.info(f"Weather async query completed for {location}")
        
        return result