"""API client for n8n Monitor integration."""
from __future__ import annotations

import logging
from typing import Any
import ssl
from urllib.parse import urlparse

import aiohttp
import certifi

from .const import API_V1_BASE, API_REST_BASE

_LOGGER = logging.getLogger(__name__)


class N8nApi:
    """n8n API client."""
    
    def __init__(
        self, 
        url: str, 
        api_key: str,
        verify_ssl: bool = True,
        timeout: int = 60,
    ) -> None:
        """Initialize the API client."""
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        
        # Parse URL to check if it's HTTP or HTTPS
        parsed_url = urlparse(self.url)
        self.is_https = parsed_url.scheme == "https"
    
    def _get_ssl_context(self) -> ssl.SSLContext | bool | None:
        """Get SSL context based on verify_ssl setting."""
        # For HTTP connections, no SSL context is needed
        if not self.is_https:
            return None
            
        # For HTTPS with SSL verification disabled
        if not self.verify_ssl:
            return False
        
        # For HTTPS with SSL verification enabled
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        return ssl_context
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        fallback_endpoint: str | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]] | None:
        """Make a request to the API."""
        headers = {
            "X-N8N-API-KEY": self.api_key,
            "Accept": "application/json",
        }
        
        url = f"{self.url}{endpoint}"
        
        # Create timeout
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        # Get SSL context
        ssl_context = self._get_ssl_context()
        
        # Create connector with appropriate settings
        if self.is_https:
            connector = aiohttp.TCPConnector(
                ssl=ssl_context,
                force_close=True,
            )
        else:
            # For HTTP, use a simple connector without SSL
            connector = aiohttp.TCPConnector(
                force_close=True,
            )
        
        try:
            async with aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
            ) as session:
                _LOGGER.debug("Making request to %s", url)
                
                async with session.request(
                    method, url, headers=headers, params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        _LOGGER.debug("Response received: %s", type(data))
                        return data
                    elif response.status == 404 and fallback_endpoint:
                        # Try fallback endpoint (REST API)
                        fallback_url = f"{self.url}{fallback_endpoint}"
                        _LOGGER.debug("Trying fallback URL: %s", fallback_url)
                        
                        async with session.request(
                            method, fallback_url, headers=headers, params=params
                        ) as fallback_response:
                            if fallback_response.status == 200:
                                data = await fallback_response.json()
                                _LOGGER.debug("Fallback response received: %s", type(data))
                                return data
                    
                    _LOGGER.error(
                        "Request failed: %s %s - Status: %s",
                        method,
                        url,
                        response.status,
                    )
                    try:
                        error_text = await response.text()
                        _LOGGER.error("Error response: %s", error_text)
                    except:
                        pass
                    return None
                    
        except aiohttp.ClientError as err:
            _LOGGER.error("Request error: %s", err)
            return None
        except Exception as err:
            _LOGGER.error("Unexpected error: %s", err)
            return None
    
    async def test_connection(self) -> bool:
        """Test the connection to n8n."""
        # Try to get workflows as a connection test
        result = await self.get_workflows(limit=1)
        return result is not None
    
    async def get_workflows(
        self, active: bool | None = None, limit: int = 100
    ) -> list[dict[str, Any]] | None:
        """Get workflows from n8n."""
        params = {"limit": limit}
        if active is not None:
            params["active"] = str(active).lower()
        
        result = await self._request(
            "GET",
            f"{API_V1_BASE}/workflows",
            params=params,
            fallback_endpoint=f"{API_REST_BASE}/workflows",
        )
        
        if isinstance(result, dict) and "data" in result:
            _LOGGER.debug("Workflows data found in 'data' field")
            return result["data"]
        elif isinstance(result, list):
            _LOGGER.debug("Workflows returned as list")
            return result
        
        _LOGGER.warning("No workflows data found in response")
        return None
    
    async def get_executions(
        self,
        status: str | None = None,
        workflow_id: str | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any] | None:
        """Get executions from n8n with pagination support."""
        params = {
            "limit": limit,
            "includeData": "false",  # Don't include execution data
        }
        
        if status:
            params["status"] = status
        if workflow_id:
            params["workflowId"] = workflow_id
        if cursor:
            params["cursor"] = cursor
        
        result = await self._request(
            "GET",
            f"{API_V1_BASE}/executions",
            params=params,
            fallback_endpoint=f"{API_REST_BASE}/executions",
        )
        
        if isinstance(result, dict):
            return result
        elif isinstance(result, list):
            # Convert list format to dict format for consistency
            return {
                "data": result,
                "nextCursor": None,
            }
        return None
    
    async def get_executions_paginated(
        self,
        status: str | None = None,
        workflow_id: str | None = None,
        limit: int = 100,
        max_pages: int = 10,
    ) -> list[dict[str, Any]]:
        """Get all executions with pagination."""
        all_executions = []
        cursor = None
        page = 0
        
        while page < max_pages:
            result = await self.get_executions(
                status=status,
                workflow_id=workflow_id,
                limit=limit,
                cursor=cursor,
            )
            
            if not result or not result.get("data"):
                break
            
            all_executions.extend(result["data"])
            
            # Check for next cursor
            cursor = result.get("nextCursor")
            if not cursor:
                break
            
            page += 1
        
        return all_executions
