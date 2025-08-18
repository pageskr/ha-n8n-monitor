"""API client for n8n Monitor integration."""
from __future__ import annotations

import logging
from typing import Any
import ssl
from urllib.parse import urlparse
import socket

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
        
        _LOGGER.debug("Initialized N8nApi with URL: %s (HTTPS: %s)", self.url, self.is_https)
    
    def _get_connector(self) -> aiohttp.TCPConnector:
        """Get appropriate connector based on URL scheme."""
        connector_kwargs = {
            "force_close": True,
            "enable_cleanup_closed": True,
        }
        
        if self.is_https:
            if self.verify_ssl:
                # HTTPS with SSL verification
                ssl_context = ssl.create_default_context(cafile=certifi.where())
                connector_kwargs["ssl"] = ssl_context
            else:
                # HTTPS without SSL verification
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                connector_kwargs["ssl"] = ssl_context
        else:
            # HTTP - explicitly disable SSL
            connector_kwargs["ssl"] = False
        
        return aiohttp.TCPConnector(**connector_kwargs)
    
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
            "Content-Type": "application/json",
        }
        
        url = f"{self.url}{endpoint}"
        
        # Parse URL for debugging
        parsed = urlparse(url)
        _LOGGER.debug("Parsed URL - scheme: %s, netloc: %s, path: %s", 
                     parsed.scheme, parsed.netloc, parsed.path)
        
        # Create timeout
        timeout = aiohttp.ClientTimeout(total=self.timeout, connect=30)
        
        # Get appropriate connector
        connector = self._get_connector()
        
        try:
            async with aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                trust_env=True,  # Trust system proxy settings
            ) as session:
                _LOGGER.debug("Making %s request to %s", method, url)
                
                async with session.request(
                    method, 
                    url, 
                    headers=headers, 
                    params=params,
                    ssl=False if not self.is_https else None,
                ) as response:
                    _LOGGER.debug("Response status: %s", response.status)
                    
                    if response.status == 200:
                        data = await response.json()
                        _LOGGER.debug("Response received successfully")
                        return data
                    elif response.status == 404 and fallback_endpoint:
                        # Try fallback endpoint (REST API)
                        fallback_url = f"{self.url}{fallback_endpoint}"
                        _LOGGER.debug("Trying fallback URL: %s", fallback_url)
                        
                        async with session.request(
                            method, 
                            fallback_url, 
                            headers=headers, 
                            params=params,
                            ssl=False if not self.is_https else None,
                        ) as fallback_response:
                            if fallback_response.status == 200:
                                data = await fallback_response.json()
                                _LOGGER.debug("Fallback response received successfully")
                                return data
                            else:
                                _LOGGER.error("Fallback request failed with status: %s", 
                                            fallback_response.status)
                    
                    _LOGGER.error(
                        "Request failed: %s %s - Status: %s",
                        method,
                        url,
                        response.status,
                    )
                    try:
                        error_text = await response.text()
                        _LOGGER.error("Error response: %s", error_text[:500])
                    except:
                        pass
                    return None
                    
        except aiohttp.ClientConnectorError as err:
            _LOGGER.error("Connection error for URL %s: %s (Host: %s)", 
                         url, err, err.host)
            # Try to provide more specific error information
            if hasattr(err, 'os_error') and isinstance(err.os_error, socket.gaierror):
                _LOGGER.error("DNS resolution failed for hostname: %s", parsed.netloc)
            return None
        except aiohttp.ClientError as err:
            _LOGGER.error("Client error for URL %s: %s", url, err)
            return None
        except Exception as err:
            _LOGGER.error("Unexpected error for URL %s: %s", url, err, exc_info=True)
            return None
    
    async def test_connection(self) -> bool:
        """Test the connection to n8n."""
        try:
            # Try to get workflows as a connection test
            result = await self.get_workflows(limit=1)
            return result is not None
        except Exception as err:
            _LOGGER.error("Connection test failed: %s", err)
            return False
    
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
            _LOGGER.debug("Workflows data found in 'data' field: %d items", 
                         len(result.get("data", [])))
            return result["data"]
        elif isinstance(result, list):
            _LOGGER.debug("Workflows returned as list: %d items", len(result))
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
            _LOGGER.debug("Executions returned as dict with %d items", 
                         len(result.get("data", [])))
            return result
        elif isinstance(result, list):
            _LOGGER.debug("Executions returned as list with %d items", len(result))
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
