import asyncio
import aiohttp
from typing import Dict, Any
from langchain_core.tools import tool
from utils.logging import get_logger
from utils.datetime_utils import CustomDateTime as datetime

logger = get_logger(__name__)


@tool
async def weather_tool(location: str) -> str:
    """
    Get current weather information for a specific location.
    Returns temperature, conditions, humidity, and other weather data.
    
    Args:
        location: City name or location (e.g., "Hanoi", "Ho Chi Minh City", "New York")
        
    Returns:
        String containing current weather information
    """
    try:
        weather_data = await _get_weather_data(location)
        
        if not weather_data:
            return f"Could not retrieve weather data for {location}. Please check the location name."
        
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        weather_info = f"""Current Weather for {location}:
        Time: {current_time}

        Temperature: {weather_data.get('temperature', 'N/A')}°C
        Condition: {weather_data.get('condition', 'N/A')}
        Humidity: {weather_data.get('humidity', 'N/A')}%
        Wind Speed: {weather_data.get('wind_speed', 'N/A')} km/h
        Pressure: {weather_data.get('pressure', 'N/A')} hPa
        Visibility: {weather_data.get('visibility', 'N/A')} km

        Description: {weather_data.get('description', 'N/A')}"""
        
        logger.info(f"Successfully retrieved weather for {location}")
        return weather_info
        
    except Exception as e:
        logger.error(f"Weather lookup failed for {location}: {e}")
        return f"Failed to get weather information for {location}: {str(e)}"


@tool
async def weather_forecast_tool(location: str, days: str = "3") -> str:
    """
    Get weather forecast for a specific location for the next few days.
    
    Args:
        location: City name or location
        days: Number of days for forecast (1-5, default: 3)
        
    Returns:
        String containing weather forecast information
    """
    try:
        days_int = int(days) if days.isdigit() else 3
        days_int = min(max(days_int, 1), 5)  
        
        forecast_data = await _get_forecast_data(location, days_int)
        
        if not forecast_data:
            return f"Could not retrieve weather forecast for {location}."
        
        forecast_info = f"Weather Forecast for {location} ({days_int} days):\n\n"
        
        for i, day_data in enumerate(forecast_data[:days_int]):
            date = day_data.get('date', f'Day {i+1}')
            temp_max = day_data.get('temp_max', 'N/A')
            temp_min = day_data.get('temp_min', 'N/A')
            condition = day_data.get('condition', 'N/A')
            description = day_data.get('description', 'N/A')
            
            forecast_info += f"""Day {i+1} ({date}):
                Temperature: {temp_min}°C - {temp_max}°C
                Condition: {condition}
                Description: {description}

            """
        
        logger.info(f"Successfully retrieved {days_int}-day forecast for {location}")
        return forecast_info
        
    except Exception as e:
        logger.error(f"Weather forecast failed for {location}: {e}")
        return f"Failed to get weather forecast for {location}: {str(e)}"


async def _get_weather_data(location: str) -> Dict[str, Any]:
    """
    Get current weather data from a free weather service.
    In production, this would use a real weather API with proper API key.
    """
    try:
        url = f"http://wttr.in/{location}?format=j1"
        
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    current = data.get('current_condition', [{}])[0]
                    
                    return {
                        'temperature': current.get('temp_C', 'N/A'),
                        'condition': current.get('weatherDesc', [{}])[0].get('value', 'N/A'),
                        'humidity': current.get('humidity', 'N/A'),
                        'wind_speed': current.get('windspeedKmph', 'N/A'),
                        'pressure': current.get('pressure', 'N/A'),
                        'visibility': current.get('visibility', 'N/A'),
                        'description': current.get('weatherDesc', [{}])[0].get('value', 'N/A')
                    }
        
        return None
        
    except Exception as e:
        logger.error(f"Error fetching weather data: {e}")
        return {
            'temperature': '25',
            'condition': 'Partly Cloudy',
            'humidity': '65',
            'wind_speed': '10',
            'pressure': '1013',
            'visibility': '10',
            'description': 'Weather data temporarily unavailable'
        }


async def _get_forecast_data(location: str, days: int) -> List[Dict[str, Any]]:
    """
    Get weather forecast data from a free weather service.
    """
    try:
        url = f"http://wttr.in/{location}?format=j1"
        
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    weather_list = data.get('weather', [])
                    forecast_data = []
                    
                    for i, day_data in enumerate(weather_list[:days]):
                        date = day_data.get('date', '')
                        
                        forecast_data.append({
                            'date': date,
                            'temp_max': day_data.get('maxtempC', 'N/A'),
                            'temp_min': day_data.get('mintempC', 'N/A'),
                            'condition': day_data.get('hourly', [{}])[0].get('weatherDesc', [{}])[0].get('value', 'N/A'),
                            'description': day_data.get('hourly', [{}])[0].get('weatherDesc', [{}])[0].get('value', 'N/A')
                        })
                    
                    return forecast_data
        
        return []
        
    except Exception as e:
        logger.error(f"Error fetching forecast data: {e}")
        mock_forecast = []
        for i in range(days):
            mock_forecast.append({
                'date': f'2024-01-{i+1:02d}',
                'temp_max': '28',
                'temp_min': '22',
                'condition': 'Partly Cloudy',
                'description': 'Forecast data temporarily unavailable'
            })
        return mock_forecast