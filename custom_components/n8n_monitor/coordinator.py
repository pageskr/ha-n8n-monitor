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


def get_status_key(status: str | None) -> str:
    """Normalize status string to our constants."""
    if not status:
        return STATUS_UNKNOWN
    
    status_lower = status.lower()
    
    # Map n8n status values to our constants
    if status_lower == "success":
        return STATUS_SUCCESS
    elif status_lower == "error":
        return STATUS_ERROR
    elif status_lower in ["running", "executing", "new", "waiting"]:
        return STATUS_RUNNING
    elif status_lower in ["canceled", "cancelled", "stopped"]:
        return STATUS_CANCELED
    else:
        _LOGGER.debug("Unknown status: %s", status)
        return STATUS_UNKNOWN


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
            
            # Get recent executions (without time filter in API)
            all_executions = await self.api.get_executions_paginated(
                limit=250,
                max_pages=5,  # Get up to 1250 executions
                include_data=False,  # Don't need full data for counting
            )
            
            _LOGGER.debug("Fetched %d total executions", len(all_executions))
            
            # Filter executions by time window and group by workflow
            executions_by_workflow = defaultdict(list)
            executions_in_window = 0
            
            for execution in all_executions:
                exec_time = parse_datetime(execution.get("startedAt"))
                if not exec_time:
                    continue
                
                # Only include executions within our time window
                if exec_time >= window_start:
                    workflow_id = execution.get("workflowId")
                    if workflow_id:
                        executions_by_workflow[workflow_id].append(execution)
                        executions_in_window += 1
            
            _LOGGER.debug("Executions in window (%dh): %d", self.window_hours, executions_in_window)
            
            # Process workflows
            processed_workflows = []
            active_count = 0
            
            for workflow in workflows:
                workflow_id = workflow.get("id")
                workflow_name = workflow.get("name", "Unknown")
                is_active = workflow.get("active", False)
                
                if is_active:
                    active_count += 1
                
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
                
                # Count executions by status
                for execution in workflow_executions:
                    # Get status
                    status = execution.get("status")
                    status_key = get_status_key(status)
                    recent_counts[status_key] += 1
                    
                    # Track last execution time
                    exec_time = parse_datetime(execution.get("startedAt"))
                    if exec_time and (last_execution_time is None or exec_time > last_execution_time):
                        last_execution_time = exec_time
                
                # Add processed workflow
                processed_workflow = {
                    "id": workflow_id,
                    "name": workflow_name,
                    "active": is_active,
                    "last_execution_time": (
                        last_execution_time.isoformat() if last_execution_time else None
                    ),
                    "recent_execution": recent_counts,
                }
                processed_workflows.append(processed_workflow)
            
            result = {
                "items": processed_workflows,
                "total": len(processed_workflows),
                "active": active_count,
                "generated_at": now.isoformat(),
                "execution_hours": self.window_hours,
            }
            
            _LOGGER.debug("Returning workflow data with %d items (%d active)", 
                         len(processed_workflows), active_count)
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
        self.page_size = min(page_size, 250)  # API limit
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
            total_fetched = 0
            executions_in_window = 0
            
            _LOGGER.debug("Starting to fetch executions with window %d hours", self.window_hours)
            
            while pages_fetched < max_pages:
                result = await self.api.get_executions(
                    limit=self.page_size,
                    cursor=cursor,
                    include_data=True,  # Need data for error messages and workflow names
                )
                
                if not result or not result.get("data"):
                    _LOGGER.debug("No more executions to fetch")
                    break
                
                page_executions = result["data"]
                total_fetched += len(page_executions)
                _LOGGER.debug("Fetched %d executions on page %d (total: %d)", 
                            len(page_executions), pages_fetched + 1, total_fetched)
                
                # Process executions
                all_outside_window = True
                
                for execution in page_executions:
                    # Parse execution time
                    exec_time = parse_datetime(execution.get("startedAt"))
                    if not exec_time:
                        continue
                    
                    # Check if within window
                    if exec_time >= window_start:
                        all_outside_window = False
                        executions_in_window += 1
                        
                        # Get status and normalize it
                        status = execution.get("status")
                        status_key = get_status_key(status)
                        
                        # Calculate duration
                        duration_ms = None
                        finished_at = execution.get("finishedAt") or execution.get("stoppedAt")
                        if finished_at:
                            stopped_at = parse_datetime(finished_at)
                            if stopped_at and exec_time:
                                duration_ms = int((stopped_at - exec_time).total_seconds() * 1000)
                        
                        # Get workflow name from execution data
                        workflow_name = "Unknown"
                        if execution.get("data") and isinstance(execution["data"], dict):
                            workflow_data = execution["data"].get("workflowData", {})
                            if isinstance(workflow_data, dict):
                                workflow_name = workflow_data.get("name", "Unknown")
                        
                        # Add to appropriate list
                        exec_data = {
                            "id": execution.get("id"),
                            "workflowId": execution.get("workflowId"),
                            "workflowName": workflow_name,
                            "startedAt": execution.get("startedAt"),
                            "finishedAt": finished_at,
                            "duration_ms": duration_ms,
                        }
                        
                        # Add error message for failed executions
                        if status_key == STATUS_ERROR:
                            error_msg = "Unknown error"
                            if execution.get("data") and isinstance(execution["data"], dict):
                                result_data = execution["data"].get("resultData", {})
                                if isinstance(result_data, dict):
                                    error_obj = result_data.get("error")
                                    if isinstance(error_obj, dict):
                                        error_msg = error_obj.get("message", "Unknown error")
                                    elif isinstance(error_obj, str):
                                        error_msg = error_obj
                                    
                                    # Also check for lastNodeExecuted for more context
                                    last_node = result_data.get("lastNodeExecuted")
                                    if last_node and error_msg == "Unknown error":
                                        error_msg = f"Error at node: {last_node}"
                            
                            exec_data["error"] = error_msg
                        
                        executions_by_status[status_key].append(exec_data)
                        
                        if status_key == STATUS_UNKNOWN:
                            _LOGGER.debug("Unknown status for execution %s: %s", 
                                        execution.get("id"), status)
                
                # If all executions in this page are outside the window, we can stop
                # (assuming executions are sorted by startedAt descending)
                if all_outside_window and pages_fetched > 0:
                    _LOGGER.debug("All executions in page are outside window, stopping pagination")
                    break
                
                # Check for next cursor
                cursor = result.get("nextCursor")
                if not cursor:
                    break
                
                pages_fetched += 1
            
            _LOGGER.debug("Total executions fetched: %d, in window: %d", 
                         total_fetched, executions_in_window)
            
            # Prepare final data with trimming
            final_data = {
                "window": f"{self.window_hours}h",
                "generated_at": now.isoformat(),
            }
            
            # Add status data
            for status in [STATUS_SUCCESS, STATUS_ERROR, STATUS_RUNNING, STATUS_CANCELED, STATUS_UNKNOWN]:
                items = executions_by_status.get(status, [])
                
                # Sort by startedAt descending (most recent first)
                items.sort(key=lambda x: x.get("startedAt", ""), reverse=True)
                
                # Trim to attr_limit
                trimmed_items = items[:self.attr_limit] if len(items) > self.attr_limit else items
                
                # Always include count and items for all statuses
                final_data[status] = {
                    "count": len(items),
                    "items": trimmed_items,
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
            
            _LOGGER.info("Execution summary - Total: %d, Success: %d, Error: %d, Running: %d, Canceled: %d, Unknown: %d",
                        total,
                        len(executions_by_status.get(STATUS_SUCCESS, [])),
                        len(executions_by_status.get(STATUS_ERROR, [])),
                        len(executions_by_status.get(STATUS_RUNNING, [])),
                        len(executions_by_status.get(STATUS_CANCELED, [])),
                        len(executions_by_status.get(STATUS_UNKNOWN, [])))
            
            return result
            
        except Exception as err:
            _LOGGER.error("Error updating executions data: %s", err, exc_info=True)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
