"""Constants for n8n Monitor integration."""
from typing import Final

# Domain
DOMAIN: Final = "n8n_monitor"

# Manufacturer
MANUFACTURER: Final = "Pages in Korea (pages.kr)"

# Configuration keys
CONF_DEVICE_NAME: Final = "device_name"
CONF_API_KEY: Final = "api_key"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_WINDOW_HOURS: Final = "window_hours"
CONF_PAGE_SIZE: Final = "page_size"
CONF_ATTR_LIMIT: Final = "attr_limit"
CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_REQUEST_TIMEOUT: Final = "request_timeout"

# Default values
DEFAULT_SCAN_INTERVAL: Final = 300  # 5 minutes
DEFAULT_WINDOW_HOURS: Final = 6  # 6 hours
DEFAULT_PAGE_SIZE: Final = 100
DEFAULT_ATTR_LIMIT: Final = 50
DEFAULT_VERIFY_SSL: Final = True
DEFAULT_REQUEST_TIMEOUT: Final = 60  # 60 seconds

# Data keys
DATA_COORDINATOR_WORKFLOWS: Final = "coordinator_workflows"
DATA_COORDINATOR_EXECUTIONS: Final = "coordinator_executions"

# API endpoints
API_V1_BASE: Final = "/api/v1"
API_REST_BASE: Final = "/rest"

# Execution statuses
STATUS_SUCCESS: Final = "success"
STATUS_ERROR: Final = "error"
STATUS_RUNNING: Final = "running"
STATUS_CANCELED: Final = "canceled"
STATUS_UNKNOWN: Final = "unknown"

# Device info
DEVICE_SW_VERSION: Final = "1.1.0"
