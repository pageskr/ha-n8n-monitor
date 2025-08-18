"""Config flow for n8n Monitor integration."""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

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
    CONF_VERIFY_SSL,
    CONF_REQUEST_TIMEOUT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WINDOW_HOURS,
    DEFAULT_PAGE_SIZE,
    DEFAULT_ATTR_LIMIT,
    DEFAULT_VERIFY_SSL,
    DEFAULT_REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


def validate_url(url: str) -> str:
    """Validate and normalize URL."""
    # Remove whitespace
    url = url.strip()
    
    # Parse URL
    parsed = urlparse(url)
    
    # Check if scheme is present
    if not parsed.scheme:
        raise vol.Invalid("URL must include protocol (http:// or https://)")
    
    # Check if scheme is valid
    if parsed.scheme not in ["http", "https"]:
        raise vol.Invalid("URL must use http or https protocol")
    
    # Check if netloc is present (domain/IP and optional port)
    if not parsed.netloc:
        raise vol.Invalid("Invalid URL format")
    
    # Check if the URL looks like it has the port in the wrong place
    if ":" in parsed.netloc:
        # This is correct - hostname:port format
        parts = parsed.netloc.split(":")
        if len(parts) == 2:
            hostname, port = parts
            try:
                port_num = int(port)
                if port_num < 1 or port_num > 65535:
                    raise vol.Invalid(f"Invalid port number: {port}")
            except ValueError:
                raise vol.Invalid(f"Invalid port number: {port}")
    
    # Reconstruct URL to ensure it's properly formatted
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    if parsed.path:
        base_url += parsed.path.rstrip("/")
    
    _LOGGER.debug("Validated URL: %s", base_url)
    return base_url


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
                # Validate URL
                url = validate_url(user_input[CONF_URL])
                user_input[CONF_URL] = url
                
                _LOGGER.debug("Testing connection to %s", url)
                
                # Test connection
                api = N8nApi(
                    url=user_input[CONF_URL],
                    api_key=user_input[CONF_API_KEY],
                    verify_ssl=user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                    timeout=DEFAULT_REQUEST_TIMEOUT,
                )
                
                if not await api.test_connection():
                    errors["base"] = "cannot_connect"
                    _LOGGER.error("Failed to connect to n8n at %s", url)
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
                            CONF_REQUEST_TIMEOUT: DEFAULT_REQUEST_TIMEOUT,
                        }
                    )
            except vol.Invalid as err:
                errors["url"] = str(err)
                _LOGGER.error("URL validation error: %s", err)
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
                vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): bool,
            }),
            errors=errors,
            description_placeholders={
                "url_example": "http://n8n:5678 or https://n8n.example.com",
            },
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
                vol.Optional(
                    CONF_REQUEST_TIMEOUT,
                    default=self.config_entry.options.get(
                        CONF_REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
                vol.Optional(
                    CONF_VERIFY_SSL,
                    default=self.config_entry.data.get(
                        CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL
                    ),
                ): bool,
            }),
        )
