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


def parse_datetime(dt_string: str | None) -> datetime | None:
    """Parse datetime string to datetime object."""
    if not dt_string:
        return None
    
    try:
        # Handle various datetime formats
        if dt_string.endswith('Z'):
            return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        else:
            return datetime.fromisoformat(dt_string)
    except (ValueError, AttributeError):
        _LOGGER.warning("Failed to parse datetime: %s", dt_string)
        return None


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
            
            _LOGGER.debug("Fetched %d workflows", len(workflows))
            
            # Get current time and window start in UTC
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(hours=self.window_hours)
            
            # First, get all recent executions in one call
            all_executions = await self.api.get_executions(limit=250)
            
            # Create a map of workflow_id to executions
            executions_by_workflow = defaultdict(list)
            if all_executions and all_executions.get("data"):
                for execution in all_executions["data"]:
                    workflow_id = execution.get("workflowId")
                    if workflow_id:
                        executions_by_workflow[workflow_id].append(execution)
            
            _LOGGER.debug("Grouped executions for %d workflows", len(executions_by_workflow))
            
            # Process workflows
            processed_workflows = []
            for workflow in workflows:
                workflow_id = workflow.get("id")
                workflow_name = workflow.get("name", "Unknown")
                
                # Get executions for this workflow
                workflow_executions = executions_by_workflow.get(workflow_id, [])
                
                recent_counts = {
                    STATUS_SUCCESS: 0,
                    STATUS_ERROR: 0,
                    STATUS_RUNNING: 0,
                    STATUS_CANCELED: 0,
                    STATUS_UNKNOWN: 0,
                }
                
                last_execution_time = None
                
                for execution in workflow_executions:
                    # Parse execution time
                    exec_time = parse_datetime(execution.get("startedAt"))
                    if not exec_time:
                        continue
                    
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
                processed_workflow = {
                    "id": workflow_id,
                    "name": workflow_name,
                    "active": workflow.get("active", False),
                    "last_execution_time": (
                        last_execution_time.isoformat() if last_execution_time else None
                    ),
                    "recent_execution": recent_counts,
                }
                processed_workflows.append(processed_workflow)
            
            result = {
                "items": processed_workflows,
                "total": len(processed_workflows),
                "generated_at": now.isoformat(),
                "execution_hours": self.window_hours,
            }
            
            _LOGGER.debug("Returning workflow data with %d items", len(processed_workflows))
            return result
            
        except Exception as err:
            _LOGGER.error("Error updating workflows data: %s", err, exc_info=True)
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
            
            _LOGGER.debug("Starting to fetch executions with window %d hours", self.window_hours)
            
            while pages_fetched < max_pages:
                result = await self.api.get_executions(
                    limit=self.page_size,
                    cursor=cursor,
                )
                
                if not result or not result.get("data"):
                    _LOGGER.debug("No more executions to fetch")
                    break
                
                _LOGGER.debug("Fetched %d executions on page %d", len(result["data"]), pages_fetched + 1)
                
                # Process executions
                should_continue = False
                for execution in result["data"]:
                    # Parse execution time
                    exec_time = parse_datetime(execution.get("startedAt"))
                    if not exec_time:
                        continue
                    
                    # Check if within window
                    if exec_time < window_start:
                        # Executions are sorted by time, so we can stop here
                        _LOGGER.debug("Reached executions outside window, stopping pagination")
                        break
                    
                    should_continue = True
                    
                    # Get status
                    status = execution.get("status", STATUS_UNKNOWN)
                    if status not in [STATUS_SUCCESS, STATUS_ERROR, STATUS_RUNNING, STATUS_CANCELED]:
                        status = STATUS_UNKNOWN
                    
                    # Calculate duration
                    duration_ms = None
                    stopped_at = parse_datetime(execution.get("stoppedAt"))
                    if stopped_at and exec_time:
                        duration_ms = int((stopped_at - exec_time).total_seconds() * 1000)
                    
                    # Add to appropriate list
                    exec_data = {
                        "id": execution.get("id"),
                        "workflowId": execution.get("workflowId"),
                        "startedAt": execution.get("startedAt"),
                        "finishedAt": execution.get("stoppedAt"),
                        "duration_ms": duration_ms,
                    }
                    
                    # Add error message for failed executions
                    if status == STATUS_ERROR:
                        error_msg = "Unknown error"
                        if isinstance(execution.get("error"), dict):
                            error_msg = execution["error"].get("message", "Unknown error")
                        elif isinstance(execution.get("error"), str):
                            error_msg = execution["error"]
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
            
            result = {
                "total": total,
                **final_data,
            }
            
            _LOGGER.debug("Returning execution data with total %d", total)
            return result
            
        except Exception as err:
            _LOGGER.error("Error updating executions data: %s", err, exc_info=True)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
