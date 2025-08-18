"""Sensor platform for n8n Monitor integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MANUFACTURER,
    DEVICE_SW_VERSION,
    CONF_DEVICE_NAME,
    CONF_SCAN_INTERVAL,
    CONF_WINDOW_HOURS,
    CONF_PAGE_SIZE,
    CONF_ATTR_LIMIT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WINDOW_HOURS,
    DEFAULT_PAGE_SIZE,
    DEFAULT_ATTR_LIMIT,
)
from .coordinator import N8nWorkflowsCoordinator, N8nExecutionsCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up n8n Monitor sensors from a config entry."""
    # Get API instance
    api = hass.data[DOMAIN][config_entry.entry_id]
    
    # Get options
    scan_interval = config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    window_hours = config_entry.options.get(CONF_WINDOW_HOURS, DEFAULT_WINDOW_HOURS)
    page_size = config_entry.options.get(CONF_PAGE_SIZE, DEFAULT_PAGE_SIZE)
    attr_limit = config_entry.options.get(CONF_ATTR_LIMIT, DEFAULT_ATTR_LIMIT)
    
    # Create coordinators
    workflows_coordinator = N8nWorkflowsCoordinator(
        hass,
        api,
        window_hours,
        timedelta(seconds=scan_interval),
    )
    
    executions_coordinator = N8nExecutionsCoordinator(
        hass,
        api,
        window_hours,
        page_size,
        attr_limit,
        timedelta(seconds=scan_interval),
    )
    
    # Fetch initial data
    await workflows_coordinator.async_config_entry_first_refresh()
    await executions_coordinator.async_config_entry_first_refresh()
    
    # Create entities
    entities = [
        N8nWorkflowsSensor(workflows_coordinator, config_entry),
        N8nExecutionsSensor(executions_coordinator, config_entry),
    ]
    
    async_add_entities(entities)


class N8nBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for n8n Monitor sensors."""
    
    _attr_has_entity_name = True
    
    def __init__(
        self,
        coordinator: N8nWorkflowsCoordinator | N8nExecutionsCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_device_info = self._get_device_info()
    
    def _get_device_info(self) -> DeviceInfo:
        """Get device information."""
        device_name = self._config_entry.data.get(
            CONF_DEVICE_NAME,
            f"n8n ({self._config_entry.data[CONF_URL]})"
        )
        
        return DeviceInfo(
            identifiers={(DOMAIN, self._config_entry.entry_id)},
            name=device_name,
            manufacturer=MANUFACTURER,
            model="n8n Workflow Automation",
            sw_version=DEVICE_SW_VERSION,
            configuration_url="https://github.com/pageskr/ha-n8n-monitor",
        )


class N8nWorkflowsSensor(N8nBaseSensor):
    """n8n workflows sensor."""
    
    _attr_name = "Workflows"
    _attr_icon = "mdi:sitemap"
    _attr_state_class = SensorStateClass.MEASUREMENT
    
    def __init__(
        self,
        coordinator: N8nWorkflowsCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.entry_id}_workflows"
    
    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get("total", 0)
        return None
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data:
            return {}
        
        return {
            "items": self.coordinator.data.get("items", []),
            "total": self.coordinator.data.get("total", 0),
            "generated_at": self.coordinator.data.get("generated_at"),
            "execution_hours": self.coordinator.data.get("execution_hours"),
        }


class N8nExecutionsSensor(N8nBaseSensor):
    """n8n executions sensor."""
    
    _attr_name = "Executions"
    _attr_icon = "mdi:play-circle"
    _attr_state_class = SensorStateClass.MEASUREMENT
    
    def __init__(
        self,
        coordinator: N8nExecutionsCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_unique_id = f"{config_entry.entry_id}_executions"
    
    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get("total", 0)
        return None
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data:
            return {}
        
        # Return all data except total (which is the state)
        attrs = dict(self.coordinator.data)
        attrs.pop("total", None)
        return attrs
