"""n8n Monitor integration for Home Assistant."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_VERIFY_SSL, CONF_REQUEST_TIMEOUT, DEFAULT_VERIFY_SSL, DEFAULT_REQUEST_TIMEOUT
from .api import N8nApi

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the n8n Monitor component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up n8n Monitor from a config entry."""
    
    hass.data.setdefault(DOMAIN, {})
    
    # Get SSL verification setting (from data for initial setup, from options for updates)
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)
    if CONF_VERIFY_SSL in entry.options:
        verify_ssl = entry.options[CONF_VERIFY_SSL]
    
    # Get timeout setting
    timeout = entry.options.get(CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT)
    
    # Create API instance
    api = N8nApi(
        url=entry.data["url"],
        api_key=entry.data["api_key"],
        verify_ssl=verify_ssl,
        timeout=timeout,
    )
    
    # Store API instance
    hass.data[DOMAIN][entry.entry_id] = api
    
    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    # Remove data
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
