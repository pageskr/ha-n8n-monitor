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
    
    # Map various status values to our constants
    if status_lower in ["success", "finished"]:
        return STATUS_SUCCESS
    elif status_lower in ["error", "failed", "crashed"]:
        return STATUS_ERROR
    elif status_lower in ["running", "executing", "new"]:
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
        page_size: int,
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
        self.page_size = page_size
        # Store shared executions data
        self._executions_data = None
    
    def set_executions_data(self, data: dict[str, Any]) -> None:
        """Set executions data from executions coordinator."""
        self._executions_data = data
    
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            workflows = await self.api.get_workflows()
            if workflows is None:
                raise UpdateFailed("Failed to fetch workflows")
            
            _LOGGER.debug("Fetched %d workflows", len(workflows))
            
            # Get current time and window start in UTC
            now = datetime.now(timezone.utc)
            
            # Use executions data if available
            executions_by_workflow = defaultdict(list)
            
            if self._executions_data:
                # Use shared executions data
                for status_key in [STATUS_SUCCESS, STATUS_ERROR, STATUS_RUNNING, STATUS_CANCELED, STATUS_UNKNOWN]:
                    status_data = self._executions_data.get(status_key, {})
                    items = status_data.get("items", [])
                    for execution in items:
                        workflow_id = execution.get("workflowId")
                        if workflow_id:
                            exec_data = {
                                "status": status_key,
                                "startedAt": execution.get("startedAt"),
                                "workflowId": workflow_id,
                            }
                            executions_by_workflow[workflow_id].append(exec_data)
                
                _LOGGER.debug("Using shared executions data for %d workflows", len(executions_by_workflow))
            
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
                
                for execution in workflow_executions:
                    # Parse execution time
                    exec_time = parse_datetime(execution.get("startedAt"))
                    if exec_time:
                        # Update last execution time
                        if last_execution_time is None or exec_time > last_execution_time:
                            last_execution_time = exec_time
                    
                    # Count by status (already normalized in executions data)
                    status = execution.get("status", STATUS_UNKNOWN)
                    recent_counts[status] += 1
                
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
        self.page_size = page_size
        self.attr_limit = attr_limit
        # Reference to workflows coordinator
        self._workflows_coordinator = None
    
    def set_workflows_coordinator(self, coordinator: N8nWorkflowsCoordinator) -> None:
        """Set reference to workflows coordinator."""
        self._workflows_coordinator = coordinator
    
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            # Get current time and window start in UTC
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(hours=self.window_hours)
            
            # Convert window_start to ISO format for API
            started_after = window_start.isoformat()
            
            # Initialize data structure
            executions_by_status = defaultdict(list)
            
            # Calculate max pages based on expected executions
            # Assuming average 50 executions per hour, calculate pages needed
            expected_executions = self.window_hours * 50
            max_pages = max(5, min(20, (expected_executions // self.page_size) + 2))
            
            _LOGGER.debug("Starting to fetch executions with window %d hours (after %s)", 
                         self.window_hours, started_after)
            
            # Fetch all executions within window
            all_executions = await self.api.get_executions_paginated(
                limit=self.page_size,
                max_pages=max_pages,
                started_after=started_after,
            )
            
            _LOGGER.debug("Fetched total %d executions", len(all_executions))
            
            # Get workflow names if needed
            workflow_names = {}
            if all_executions:
                # Get unique workflow IDs
                workflow_ids = set()
                for execution in all_executions:
                    workflow_id = execution.get("workflowId")
                    if workflow_id:
                        workflow_ids.add(workflow_id)
                
                # Try to get workflow names from workflow data
                if self._workflows_coordinator and self._workflows_coordinator.data:
                    workflows = self._workflows_coordinator.data.get("items", [])
                    for workflow in workflows:
                        workflow_names[workflow["id"]] = workflow["name"]
                else:
                    # Fallback: get workflow names from API
                    workflows = await self.api.get_workflows()
                    if workflows:
                        for workflow in workflows:
                            workflow_names[workflow.get("id")] = workflow.get("name", "Unknown")
            
            # Process executions
            for execution in all_executions:
                # Get status and normalize it
                status = execution.get("status")
                status_key = get_status_key(status)
                
                # Get workflow info
                workflow_id = execution.get("workflowId")
                workflow_name = workflow_names.get(workflow_id, "Unknown")
                
                # Parse times
                started_at = execution.get("startedAt")
                stopped_at = execution.get("stoppedAt")
                exec_time = parse_datetime(started_at)
                
                # Calculate duration
                duration_ms = None
                if stopped_at and started_at:
                    stopped_time = parse_datetime(stopped_at)
                    if stopped_time and exec_time:
                        duration_ms = int((stopped_time - exec_time).total_seconds() * 1000)
                
                # Add to appropriate list
                exec_data = {
                    "id": execution.get("id"),
                    "workflowId": workflow_id,
                    "workflowName": workflow_name,
                    "startedAt": started_at,
                    "finishedAt": stopped_at,
                    "duration_ms": duration_ms,
                }
                
                # Add error message for failed executions if available
                if status_key == STATUS_ERROR and execution.get("data"):
                    error_msg = "Unknown error"
                    if isinstance(execution.get("data"), dict):
                        result_error = execution["data"].get("resultData", {}).get("error")
                        if result_error:
                            if isinstance(result_error, dict):
                                error_msg = result_error.get("message", "Unknown error")
                            else:
                                error_msg = str(result_error)
                    exec_data["error"] = error_msg
                
                executions_by_status[status_key].append(exec_data)
                
                if status_key == STATUS_UNKNOWN:
                    _LOGGER.debug("Unknown status for execution %s: %s", 
                                execution.get("id"), status)
            
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
            
            _LOGGER.debug("Execution summary - Total: %d, Success: %d, Error: %d, Running: %d, Canceled: %d, Unknown: %d",
                         total,
                         len(executions_by_status.get(STATUS_SUCCESS, [])),
                         len(executions_by_status.get(STATUS_ERROR, [])),
                         len(executions_by_status.get(STATUS_RUNNING, [])),
                         len(executions_by_status.get(STATUS_CANCELED, [])),
                         len(executions_by_status.get(STATUS_UNKNOWN, [])))
            
            # Share data with workflows coordinator
            if self._workflows_coordinator:
                self._workflows_coordinator.set_executions_data(final_data)
            
            return result
            
        except Exception as err:
            _LOGGER.error("Error updating executions data: %s", err, exc_info=True)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
