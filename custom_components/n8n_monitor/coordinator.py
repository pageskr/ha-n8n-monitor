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
    # Based on n8n API: "error" | "success" | "waiting"
    if status_lower == "success":
        return STATUS_SUCCESS
    elif status_lower == "error":
        return STATUS_ERROR
    elif status_lower in ["running", "executing", "new", "waiting"]:
        return STATUS_RUNNING
    elif status_lower in ["canceled", "cancelled", "stopped", "crash", "crashed"]:
        return STATUS_CANCELED
    else:
        _LOGGER.warning("Unknown execution status: '%s'", status)
        return STATUS_UNKNOWN


class N8nSharedDataCoordinator(DataUpdateCoordinator):
    """Coordinator that fetches all data once and shares it."""
    
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
            name=f"{DOMAIN}_shared",
            update_interval=update_interval,
        )
        self.api = api
        self.window_hours = window_hours
        self.page_size = min(page_size, 250)  # API limit
        self.attr_limit = attr_limit
        
        # Shared data
        self.workflows_data = None
        self.executions_data = None
    
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all data from API once."""
        try:
            # Get current time and window start in UTC
            now = datetime.now(timezone.utc)
            window_start = now - timedelta(hours=self.window_hours)
            
            # 1. Fetch workflows first
            workflows = await self.api.get_workflows()
            if workflows is None:
                raise UpdateFailed("Failed to fetch workflows")
            
            _LOGGER.debug("Fetched %d workflows", len(workflows))
            
            # Create workflow ID to name mapping
            workflow_names = {}
            for workflow in workflows:
                workflow_id = workflow.get("id")
                workflow_name = workflow.get("name", "Unknown")
                if workflow_id:
                    workflow_names[str(workflow_id)] = workflow_name
            
            # 2. Fetch executions ONCE with configured limit
            all_executions = []
            result = await self.api.get_executions(
                limit=self.page_size,
                include_data=True,  # Need data for error messages
            )
            
            if result and result.get("data"):
                all_executions = result["data"]
            
            _LOGGER.info("Fetched %d executions in single API call", len(all_executions))
            
            # Log sample execution for debugging
            if all_executions:
                sample = all_executions[0]
                _LOGGER.debug("Sample execution - ID: %s, Status: '%s', WorkflowId: %s", 
                            sample.get("id"), sample.get("status"), sample.get("workflowId"))
            
            # 3. Filter executions by time window
            executions_in_window = []
            status_counts = defaultdict(int)
            
            for execution in all_executions:
                exec_time = parse_datetime(execution.get("startedAt"))
                if exec_time and exec_time >= window_start:
                    executions_in_window.append(execution)
                    # Count status for debugging
                    status = execution.get("status", "none")
                    status_counts[status] += 1
            
            _LOGGER.info("Executions in window (%dh): %d", self.window_hours, len(executions_in_window))
            _LOGGER.debug("Raw status counts: %s", dict(status_counts))
            
            # 4. Process workflows data
            executions_by_workflow = defaultdict(list)
            for execution in executions_in_window:
                workflow_id = str(execution.get("workflowId", ""))
                if workflow_id:
                    executions_by_workflow[workflow_id].append(execution)
            
            processed_workflows = []
            active_count = 0
            
            for workflow in workflows:
                workflow_id = str(workflow.get("id", ""))
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
            
            self.workflows_data = {
                "items": processed_workflows,
                "total": len(processed_workflows),
                "active": active_count,
                "generated_at": now.isoformat(),
                "execution_hours": self.window_hours,
            }
            
            # 5. Process executions data
            executions_by_status = defaultdict(list)
            
            for execution in executions_in_window:
                # Get status and normalize it
                status = execution.get("status")
                status_key = get_status_key(status)
                
                # Parse execution time
                exec_time = parse_datetime(execution.get("startedAt"))
                if not exec_time:
                    continue
                
                # Calculate duration
                duration_ms = None
                finished_at = execution.get("finishedAt") or execution.get("stoppedAt")
                if finished_at:
                    stopped_at = parse_datetime(finished_at)
                    if stopped_at and exec_time:
                        duration_ms = int((stopped_at - exec_time).total_seconds() * 1000)
                
                # Get workflow name - try multiple sources
                workflow_id = str(execution.get("workflowId", ""))
                workflow_name = workflow_names.get(workflow_id, "Unknown")
                
                # If still unknown, try to get from execution data
                if workflow_name == "Unknown" and execution.get("data"):
                    if isinstance(execution["data"], dict):
                        # Try workflowData.name
                        workflow_data = execution["data"].get("workflowData")
                        if isinstance(workflow_data, dict) and workflow_data.get("name"):
                            workflow_name = workflow_data["name"]
                        # Try data.name as fallback
                        elif execution["data"].get("name"):
                            workflow_name = execution["data"]["name"]
                
                # Add to appropriate list
                exec_data = {
                    "id": execution.get("id"),
                    "workflowId": workflow_id,
                    "workflowName": workflow_name,
                    "startedAt": execution.get("startedAt"),
                    "finishedAt": finished_at,
                    "duration_ms": duration_ms,
                }
                
                # Add error message for failed executions
                if status_key == STATUS_ERROR:
                    error_msg = "Unknown error"
                    if execution.get("data") and isinstance(execution["data"], dict):
                        # Try to get error from resultData
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
                        
                        # Try to get error from data.error as fallback
                        elif execution["data"].get("error"):
                            if isinstance(execution["data"]["error"], dict):
                                error_msg = execution["data"]["error"].get("message", "Unknown error")
                            else:
                                error_msg = str(execution["data"]["error"])
                    
                    exec_data["error"] = error_msg
                
                executions_by_status[status_key].append(exec_data)
            
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
            
            self.executions_data = {
                "total": total,
                **final_data,
            }
            
            _LOGGER.info("Data update complete - Workflows: %d, Executions in window: %d",
                        len(workflows), total)
            _LOGGER.info("Execution status breakdown - Success: %d, Error: %d, Running: %d, Canceled: %d, Unknown: %d",
                        len(executions_by_status.get(STATUS_SUCCESS, [])),
                        len(executions_by_status.get(STATUS_ERROR, [])),
                        len(executions_by_status.get(STATUS_RUNNING, [])),
                        len(executions_by_status.get(STATUS_CANCELED, [])),
                        len(executions_by_status.get(STATUS_UNKNOWN, [])))
            
            # Return combined data
            return {
                "workflows": self.workflows_data,
                "executions": self.executions_data,
            }
            
        except Exception as err:
            _LOGGER.error("Error updating data: %s", err, exc_info=True)
            raise UpdateFailed(f"Error communicating with API: {err}") from err


class N8nWorkflowsCoordinator(DataUpdateCoordinator):
    """Coordinator for n8n workflows data."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        shared_coordinator: N8nSharedDataCoordinator,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_workflows",
            update_interval=None,  # We don't update independently
        )
        self.shared_coordinator = shared_coordinator
    
    async def _async_update_data(self) -> dict[str, Any]:
        """Return workflows data from shared coordinator."""
        if self.shared_coordinator.workflows_data:
            return self.shared_coordinator.workflows_data
        return {}


class N8nExecutionsCoordinator(DataUpdateCoordinator):
    """Coordinator for n8n executions data."""
    
    def __init__(
        self,
        hass: HomeAssistant,
        shared_coordinator: N8nSharedDataCoordinator,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_executions",
            update_interval=None,  # We don't update independently
        )
        self.shared_coordinator = shared_coordinator
    
    async def _async_update_data(self) -> dict[str, Any]:
        """Return executions data from shared coordinator."""
        if self.shared_coordinator.executions_data:
            return self.shared_coordinator.executions_data
        return {}
