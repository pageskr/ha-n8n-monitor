"""Data coordinator for n8n Monitor integration."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import N8nApi
from .const import (
    DOMAIN,
    STATUS_SUCCESS,
    STATUS_ERROR,
    STATUS_RUNNING,
    STATUS_CANCELED,
    STATUS_UNKNOWN,
)

_LOGGER = logging.getLogger(__name__)


class N8nWorkflowsCoordinator(DataUpdateCoordinator):
    """Coordinator for n8n workflows data."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        api: N8nApi,
        window_hours: int,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_workflows",
            update_interval=update_interval,
        )
        self.api = api
        self.window_hours = window_hours
    
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            workflows = await self.api.get_workflows()
            if workflows is None:
                raise UpdateFailed("Failed to fetch workflows")
            
            # Get current time and window start in UTC
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(hours=self.window_hours)
            
            # Process workflows
            processed_workflows = []
            for workflow in workflows:
                # Get recent executions for this workflow
                executions = await self.api.get_executions(
                    workflow_id=workflow.get("id"),
                    limit=100,
                )
                
                recent_counts = {
                    STATUS_SUCCESS: 0,
                    STATUS_ERROR: 0,
                    STATUS_RUNNING: 0,
                    STATUS_CANCELED: 0,
                    STATUS_UNKNOWN: 0,
                }
                
                last_execution_time = None
                
                if executions and executions.get("data"):
                    for execution in executions["data"]:
                        # Parse execution time
                        started_at = execution.get("startedAt")
                        if started_at:
                            exec_time = datetime.fromisoformat(
                                started_at.replace("Z", "+00:00")
                            )
                            
                            # Update last execution time
                            if last_execution_time is None or exec_time > last_execution_time:
                                last_execution_time = exec_time
                            
                            # Count if within window
                            if exec_time >= window_start:
                                status = execution.get("status", STATUS_UNKNOWN)
                                if status in recent_counts:
                                    recent_counts[status] += 1
                                else:
                                    recent_counts[STATUS_UNKNOWN] += 1
                
                # Add processed workflow
                processed_workflows.append({
                    "id": workflow.get("id"),
                    "name": workflow.get("name"),
                    "active": workflow.get("active", False),
                    "last_execution_time": (
                        last_execution_time.isoformat() if last_execution_time else None
                    ),
                    "recent_execution": recent_counts,
                })
            
            return {
                "items": processed_workflows,
                "total": len(processed_workflows),
                "generated_at": now.isoformat(),
                "execution_hours": self.window_hours,
            }
        
        except Exception as err:
            _LOGGER.error("Error updating workflows data: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err


class N8nExecutionsCoordinator(DataUpdateCoordinator):
    """Coordinator for n8n executions data."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        api: N8nApi,
        window_hours: int,
        page_size: int,
        attr_limit: int,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_executions",
            update_interval=update_interval,
        )
        self.api = api
        self.window_hours = window_hours
        self.page_size = page_size
        self.attr_limit = attr_limit
    
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            # Get current time and window start in UTC
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(hours=self.window_hours)
            
            # Initialize data structure
            executions_by_status = defaultdict(list)
            
            # Fetch executions with pagination
            cursor = None
            pages_fetched = 0
            max_pages = 20  # Safety limit
            
            while pages_fetched < max_pages:
                result = await self.api.get_executions(
                    limit=self.page_size,
                    cursor=cursor,
                )
                
                if not result or not result.get("data"):
                    break
                
                # Process executions
                should_continue = False
                for execution in result["data"]:
                    # Parse execution time
                    started_at = execution.get("startedAt")
                    if not started_at:
                        continue
                    
                    exec_time = datetime.fromisoformat(
                        started_at.replace("Z", "+00:00")
                    )
                    
                    # Check if within window
                    if exec_time < window_start:
                        # Executions are sorted by time, so we can stop here
                        break
                    
                    should_continue = True
                    
                    # Get status
                    status = execution.get("status", STATUS_UNKNOWN)
                    if status not in [STATUS_SUCCESS, STATUS_ERROR, STATUS_RUNNING, STATUS_CANCELED]:
                        status = STATUS_UNKNOWN
                    
                    # Calculate duration
                    duration_ms = None
                    if execution.get("stoppedAt"):
                        stopped_at = datetime.fromisoformat(
                            execution["stoppedAt"].replace("Z", "+00:00")
                        )
                        duration_ms = int((stopped_at - exec_time).total_seconds() * 1000)
                    
                    # Add to appropriate list
                    exec_data = {
                        "id": execution.get("id"),
                        "workflowId": execution.get("workflowId"),
                        "startedAt": started_at,
                        "finishedAt": execution.get("stoppedAt"),
                        "duration_ms": duration_ms,
                    }
                    
                    # Add error message for failed executions
                    if status == STATUS_ERROR:
                        error_msg = execution.get("error", {}).get("message", "Unknown error")
                        exec_data["error"] = error_msg
                    
                    executions_by_status[status].append(exec_data)
                
                # Check if we should continue pagination
                if not should_continue:
                    break
                
                cursor = result.get("nextCursor")
                if not cursor:
                    break
                
                pages_fetched += 1
            
            # Prepare final data with trimming
            final_data = {
                "window": f"{self.window_hours}h",
                "generated_at": now.isoformat(),
            }
            
            # Add status data
            for status in [STATUS_SUCCESS, STATUS_ERROR, STATUS_RUNNING, STATUS_CANCELED, STATUS_UNKNOWN]:
                items = executions_by_status.get(status, [])
                
                # Trim to attr_limit
                trimmed_items = items[:self.attr_limit] if len(items) > self.attr_limit else items
                
                if status in [STATUS_SUCCESS, STATUS_ERROR]:
                    final_data[status] = {
                        "count": len(items),
                        "items": trimmed_items,
                    }
                else:
                    final_data[status] = {
                        "count": len(items),
                    }
            
            # Calculate total
            total = sum(
                len(executions_by_status.get(status, []))
                for status in [STATUS_SUCCESS, STATUS_ERROR, STATUS_RUNNING, STATUS_CANCELED, STATUS_UNKNOWN]
            )
            
            return {
                "total": total,
                **final_data,
            }
        
        except Exception as err:
            _LOGGER.error("Error updating executions data: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
