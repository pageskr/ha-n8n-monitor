"""API client for n8n Monitor integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import async_timeout

from .const import API_V1_BASE, API_REST_BASE

_LOGGER = logging.getLogger(__name__)


class N8nApi:
    """n8n API client."""
    
    def __init__(self, url: str, api_key: str) -> None:
        """Initialize the API client."""
        self.url = url.rstrip("/")
        self.api_key = api_key
        self._session: aiohttp.ClientSession | None = None
    
    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure we have an active session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self) -> None:
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        fallback_endpoint: str | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]] | None:
        """Make a request to the API."""
        session = await self._ensure_session()
        headers = {
            "X-N8N-API-KEY": self.api_key,
            "Accept": "application/json",
        }
        
        url = f"{self.url}{endpoint}"
        
        try:
            async with async_timeout.timeout(30):
                async with session.request(
                    method, url, headers=headers, params=params
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    elif response.status == 404 and fallback_endpoint:
                        # Try fallback endpoint (REST API)
                        fallback_url = f"{self.url}{fallback_endpoint}"
                        async with session.request(
                            method, fallback_url, headers=headers, params=params
                        ) as fallback_response:
                            if fallback_response.status == 200:
                                return await fallback_response.json()
                    
                    _LOGGER.error(
                        "Request failed: %s %s - Status: %s",
                        method,
                        url,
                        response.status,
                    )
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
            return result["data"]
        elif isinstance(result, list):
            return result
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
