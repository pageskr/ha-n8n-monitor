"""Config flow for n8n Monitor integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    CONF_API_KEY,
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

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for n8n Monitor."""
    
    VERSION = 1
    
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            # Import api module here to avoid circular imports
            from .api import N8nApi
            
            try:
                # Test connection
                api = N8nApi(
                    url=user_input[CONF_URL],
                    api_key=user_input[CONF_API_KEY]
                )
                
                if not await api.test_connection():
                    errors["base"] = "cannot_connect"
                else:
                    # Create unique ID based on URL and API key
                    await self.async_set_unique_id(
                        f"{user_input[CONF_URL]}_{user_input[CONF_API_KEY][:8]}"
                    )
                    self._abort_if_unique_id_configured()
                    
                    # Get title
                    title = user_input.get(CONF_DEVICE_NAME) or f"n8n ({user_input[CONF_URL]})"
                    
                    return self.async_create_entry(
                        title=title,
                        data=user_input,
                        options={
                            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                            CONF_WINDOW_HOURS: DEFAULT_WINDOW_HOURS,
                            CONF_PAGE_SIZE: DEFAULT_PAGE_SIZE,
                            CONF_ATTR_LIMIT: DEFAULT_ATTR_LIMIT,
                        }
                    )
            except Exception as err:
                _LOGGER.exception("Unexpected exception: %s", err)
                errors["base"] = "unknown"
        
        # Show form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_URL): str,
                vol.Required(CONF_API_KEY): str,
                vol.Optional(CONF_DEVICE_NAME): str,
            }),
            errors=errors,
        )
    
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for n8n Monitor."""
    
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
    
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
                vol.Optional(
                    CONF_WINDOW_HOURS,
                    default=self.config_entry.options.get(
                        CONF_WINDOW_HOURS, DEFAULT_WINDOW_HOURS
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=168)),
                vol.Optional(
                    CONF_PAGE_SIZE,
                    default=self.config_entry.options.get(
                        CONF_PAGE_SIZE, DEFAULT_PAGE_SIZE
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=500)),
                vol.Optional(
                    CONF_ATTR_LIMIT,
                    default=self.config_entry.options.get(
                        CONF_ATTR_LIMIT, DEFAULT_ATTR_LIMIT
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=200)),
            }),
        )
