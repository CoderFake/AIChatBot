"""
Web Search Tool implementation
"""
import json
import requests
from typing import Dict, Any, Optional, Type, List
from langchain_core.tools import BaseTool
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from pydantic import BaseModel, Field
import aiohttp
import asyncio
from models.models import WebSearchInput
from utils.logging import get_logger

logger = get_logger(__name__)

class WebSearchTool(BaseTool):
    """
    Web search tool for finding information on the internet
    Supports multiple search engines with DuckDuckGo as default (no API key required)
    """
    name: str = "web_search"
    description: str = "Searches the web for information using various search engines. Returns relevant web results."
    args_schema: Type[BaseModel] = WebSearchInput
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("Initialized web search tool")

    def _search_duckduckgo(self, query: str, num_results: int = 5, region: str = "wt-wt", time_range: Optional[str] = None) -> List[Dict]:
        """Search using DuckDuckGo (no API key required)"""
        try:
            from duckduckgo_search import DDGS
            
            search_params = {
                "keywords": query,
                "region": region,
                "max_results": min(num_results, 10)
            }
            
            if time_range:
                search_params["timelimit"] = time_range
            
            with DDGS() as ddgs:
                results = list(ddgs.text(**search_params))
                
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "title": result.get("title", ""),
                    "url": result.get("href", ""),
                    "snippet": result.get("body", ""),
                    "source": "DuckDuckGo"
                })
                
            return formatted_results
            
        except ImportError:
            logger.error("duckduckgo-search package not installed")
            return []
        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
            return []

    def _search_google_serper(self, query: str, num_results: int = 5) -> List[Dict]:
        """Search using Google Serper API (requires API key)"""
        try:
            import os
            api_key = os.getenv("SERPER_API_KEY")
            
            if not api_key:
                logger.warning("No Serper API key found")
                return []
            
            url = "https://google.serper.dev/search"
            
            payload = {
                "q": query,
                "num": min(num_results, 10)
            }
            
            headers = {
                "X-API-KEY": api_key,
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("organic", [])
                
                formatted_results = []
                for result in results:
                    formatted_results.append({
                        "title": result.get("title", ""),
                        "url": result.get("link", ""),
                        "snippet": result.get("snippet", ""),
                        "source": "Google"
                    })
                
                return formatted_results
            else:
                logger.error(f"Google Serper API error: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Google Serper search error: {e}")
            return []

    def _search_bing(self, query: str, num_results: int = 5) -> List[Dict]:
        """Search using Bing Search API (requires API key)"""
        try:
            import os
            api_key = os.getenv("BING_SEARCH_API_KEY")
            
            if not api_key:
                logger.warning("No Bing Search API key found")
                return []
            
            url = "https://api.bing.microsoft.com/v7.0/search"
            
            headers = {
                "Ocp-Apim-Subscription-Key": api_key
            }
            
            params = {
                "q": query,
                "count": min(num_results, 10),
                "mkt": "en-US"
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                results = data.get("webPages", {}).get("value", [])
                
                formatted_results = []
                for result in results:
                    formatted_results.append({
                        "title": result.get("name", ""),
                        "url": result.get("url", ""),
                        "snippet": result.get("snippet", ""),
                        "source": "Bing"
                    })
                
                return formatted_results
            else:
                logger.error(f"Bing Search API error: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Bing search error: {e}")
            return []

    def _format_results(self, results: List[Dict], query: str) -> str:
        """Format search results into readable text"""
        if not results:
            return f"No search results found for query: '{query}'"
        
        formatted = f"Search results for '{query}':\n\n"
        
        for i, result in enumerate(results, 1):
            title = result.get("title", "No title")
            url = result.get("url", "")
            snippet = result.get("snippet", "No description available")
            source = result.get("source", "Unknown")
            
            formatted += f"{i}. **{title}**\n"
            formatted += f"   URL: {url}\n"
            formatted += f"   Description: {snippet}\n"
            formatted += f"   Source: {source}\n\n"
        
        return formatted.strip()

    def _perform_search(self, query: str, num_results: int, search_engine: str, region: str, time_range: Optional[str]) -> str:
        """Perform the actual web search"""
        if not query.strip():
            return "Error: Search query cannot be empty"
        
        logger.info(f"Searching for '{query}' using {search_engine}")
        
        results = []
        
        if search_engine.lower() == "duckduckgo":
            results = self._search_duckduckgo(query, num_results, region, time_range)
        elif search_engine.lower() == "google":
            results = self._search_google_serper(query, num_results)
        elif search_engine.lower() == "bing":
            results = self._search_bing(query, num_results)
        else:
            logger.warning(f"Unknown search engine '{search_engine}', using DuckDuckGo")
            results = self._search_duckduckgo(query, num_results, region, time_range)
        
        if not results:
            if search_engine.lower() != "duckduckgo":
                logger.info("Falling back to DuckDuckGo search")
                results = self._search_duckduckgo(query, num_results, region, time_range)
        
        return self._format_results(results, query)

    async def _search_duckduckgo_async(self, query: str, num_results: int = 5, region: str = "wt-wt", time_range: Optional[str] = None) -> List[Dict]:
        """Search using DuckDuckGo asynchronously"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, 
                self._search_duckduckgo, 
                query, 
                num_results, 
                region, 
                time_range
            )
        except Exception as e:
            logger.error(f"DuckDuckGo async search error: {e}")
            return []

    async def _search_google_serper_async(self, query: str, num_results: int = 5) -> List[Dict]:
        """Search using Google Serper API asynchronously"""
        try:
            import os
            api_key = os.getenv("SERPER_API_KEY")
            
            if not api_key:
                logger.warning("No Serper API key found")
                return []
            
            url = "https://google.serper.dev/search"
            
            payload = {
                "q": query,
                "num": min(num_results, 10)
            }
            
            headers = {
                "X-API-KEY": api_key,
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = data.get("organic", [])
                        
                        formatted_results = []
                        for result in results:
                            formatted_results.append({
                                "title": result.get("title", ""),
                                "url": result.get("link", ""),
                                "snippet": result.get("snippet", ""),
                                "source": "Google"
                            })
                        
                        return formatted_results
                    else:
                        logger.error(f"Google Serper API async error: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Google Serper async search error: {e}")
            return []

    async def _search_bing_async(self, query: str, num_results: int = 5) -> List[Dict]:
        """Search using Bing Search API asynchronously"""
        try:
            import os
            api_key = os.getenv("BING_SEARCH_API_KEY")
            
            if not api_key:
                logger.warning("No Bing Search API key found")
                return []
            
            url = "https://api.bing.microsoft.com/v7.0/search"
            
            headers = {
                "Ocp-Apim-Subscription-Key": api_key
            }
            
            params = {
                "q": query,
                "count": min(num_results, 10),
                "mkt": "en-US"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        data = await response.json()
                        results = data.get("webPages", {}).get("value", [])
                        
                        formatted_results = []
                        for result in results:
                            formatted_results.append({
                                "title": result.get("name", ""),
                                "url": result.get("url", ""),
                                "snippet": result.get("snippet", ""),
                                "source": "Bing"
                            })
                        
                        return formatted_results
                    else:
                        logger.error(f"Bing Search API async error: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Bing async search error: {e}")
            return []

    async def _perform_search_async(self, query: str, num_results: int, search_engine: str, region: str, time_range: Optional[str]) -> str:
        """Perform the actual web search asynchronously"""
        if not query.strip():
            return "Error: Search query cannot be empty"
        
        logger.info(f"Searching async for '{query}' using {search_engine}")
        
        results = []
        
        if search_engine.lower() == "duckduckgo":
            results = await self._search_duckduckgo_async(query, num_results, region, time_range)
        elif search_engine.lower() == "google":
            results = await self._search_google_serper_async(query, num_results)
        elif search_engine.lower() == "bing":
            results = await self._search_bing_async(query, num_results)
        else:
            logger.warning(f"Unknown search engine '{search_engine}', using DuckDuckGo")
            results = await self._search_duckduckgo_async(query, num_results, region, time_range)
        
        if not results:
            if search_engine.lower() != "duckduckgo":
                logger.info("Falling back to DuckDuckGo async search")
                results = await self._search_duckduckgo_async(query, num_results, region, time_range)
        
        return self._format_results(results, query)

    def _run(
        self,
        query: str,
        num_results: int = 5,
        search_engine: str = "duckduckgo",
        region: str = "wt-wt",
        time_range: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """
        Execute web search synchronously
        
        Args:
            query: Search query
            num_results: Number of results to return
            search_engine: Search engine to use
            region: Region code for search
            time_range: Time range filter
            run_manager: Optional callback manager for tool run
            
        Returns:
            Formatted search results
        """
        return self._perform_search(query, num_results, search_engine, region, time_range)

    async def _arun(
        self,
        query: str,
        num_results: int = 5,
        search_engine: str = "duckduckgo",
        region: str = "wt-wt",
        time_range: Optional[str] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """
        Execute web search asynchronously
        
        Args:
            query: Search query
            num_results: Number of results to return
            search_engine: Search engine to use
            region: Region code for search
            time_range: Time range filter
            run_manager: Optional async callback manager for tool run
            
        Returns:
            Formatted search results
        """
        return await self._perform_search_async(query, num_results, search_engine, region, time_range)