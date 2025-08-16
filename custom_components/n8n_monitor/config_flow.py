"""Config flow for n8n Monitor integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
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
from .api import N8nApi

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    api = N8nApi(
        url=data[CONF_URL],
        api_key=data[CONF_API_KEY]
    )
    
    # Test connection
    if not await api.test_connection():
        raise CannotConnect
    
    # Return info to use in the config entry
    return {"title": data.get(CONF_DEVICE_NAME, f"n8n ({data[CONF_URL]})")}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for n8n Monitor."""
    
    VERSION = 1
    
    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)
    
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Create unique ID based on URL and API key
                await self.async_set_unique_id(
                    f"{user_input[CONF_URL]}_{user_input[CONF_API_KEY][:8]}"
                )
                self._abort_if_unique_id_configured()
                
                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                    options={
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        CONF_WINDOW_HOURS: DEFAULT_WINDOW_HOURS,
                        CONF_PAGE_SIZE: DEFAULT_PAGE_SIZE,
                        CONF_ATTR_LIMIT: DEFAULT_ATTR_LIMIT,
                    }
                )
        
        # Show form
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_URL): cv.url,
                vol.Required(CONF_API_KEY): cv.string,
                vol.Optional(CONF_DEVICE_NAME): cv.string,
            }),
            errors=errors,
        )


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
