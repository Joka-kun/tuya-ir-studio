"""Tuya IR Studio onboarding with Tuya / Smart Life account assistance."""
from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    QrCodeSelector,
    QrCodeSelectorConfig,
    QrErrorCorrectionLevel,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN
from .native_transport import NativeIRHub, normalize_node_id
from .tuya_cloud import TuyaCloud, resolve_hub_target

_LOGGER = logging.getLogger(__name__)

# Keep the upstream Tuya protocol candidate versions and order.
API_PROTOCOL_VERSIONS = (3.3, 3.1, 3.2, 3.4, 3.5, 3.22, 3.42, 3.52)


class IRStudioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a native Tuya IR hub and register the IR Studio panel."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Expose native HA management without requiring the sidebar panel."""
        from .options_flow import IRStudioOptionsFlow
        return IRStudioOptionsFlow()

    def __init__(self):
        self._cloud: TuyaCloud | None = None
        self._cloud_devices: dict = {}
        self._hub_data: dict = {}
        self._qr_token: str | None = None
        self._scan_failed = False

    async def async_step_user(self, user_input=None):
        """Show the Tuya Local-style setup choice before creating any entry."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("setup_mode", default="cloud"): SelectSelector(
                            SelectSelectorConfig(
                                options=["cloud", "manual", "cloud_fresh_login"],
                                mode=SelectSelectorMode.LIST,
                                translation_key="setup_mode",
                            )
                        )
                    }
                ),
            )

        mode = user_input.get("setup_mode", "cloud")
        if mode == "manual":
            self._hub_data = {}
            self._scan_failed = False
            return await self.async_step_native_hub()

        # Also works when the config flow starts before an existing native
        # hub is reloaded. Restored auth is private and never shown in UI.
        from .tuya_cloud import async_restore_cloud_auth
        await async_restore_cloud_auth(self.hass)
        self._cloud = TuyaCloud(
            self.hass,
            use_tuya_local_cache=(mode != "cloud_fresh_login"),
        )
        if mode == "cloud_fresh_login":
            # Explicit re-login must NOT destroy an otherwise valid session
            # until the new QR has actually been confirmed and saved.
            return await self.async_step_cloud()

        if self._cloud.is_authenticated:
            try:
                self._cloud_devices = await self._cloud.async_get_devices()
                self._mark_existing_devices()
                return await self.async_step_choose_device()
            except Exception as exc:
                _LOGGER.warning(
                    "Cached Tuya login could not list devices (%s)",
                    type(exc).__name__,
                    exc_info=True,
                )
                # Network/device-cache failure is not a logout event.
                # Keep tokens so the user can retry without scanning QR.

        return await self.async_step_cloud()

    def _mark_existing_devices(self):
        """Hide only the exact parent/child targets already configured."""
        configured = {
            (
                entry.data.get("device_id"),
                entry.data.get("node_id") or None,
            )
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.data.get("kind") == "native_hub"
        }
        for device in self._cloud_devices.values():
            child_id = device.get("node_id") or (device.get("uuid") if not device.get("is_hub") else None)
            device["exists"] = (device.get("id"), child_id) in configured

        # The Sharing SDK may return virtual IR children but omit their parent
        # hubs. Offer already configured native LAN gateways as parent choices
        # without modifying their config entries or disclosing secrets to the
        # IR Studio panel. They stay hidden in the first "Device" dropdown.
        known_hubs = {
            str(device.get("id"))
            for device in self._cloud_devices.values()
            if device.get("is_hub")
        }
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            data = entry.data
            if data.get("kind") != "native_hub":
                continue
            device_id = str(data.get("device_id") or "")
            if not device_id or device_id in known_hubs:
                continue
            existing_key = f"configured_hub:{entry.entry_id}"
            self._cloud_devices[existing_key] = {
                "id": device_id,
                "name": entry.title or "Настроенный ИК-шлюз HA",
                "category": "configured_gateway",
                "product_name": "Уже подключён в Home Assistant",
                "local_key": data.get("local_key") or "",
                "ip": data.get("host") or "",
                "is_hub": True,
                "exists": True,
                "online": False,
                "node_id": "",
                "uuid": "",
            }
            known_hubs.add(device_id)

    async def async_step_cloud(self, user_input=None):
        """Request the Tuya / Smart Life user code before showing the QR."""
        errors = {}
        if user_input is not None:
            try:
                self._qr_token = await self._cloud.async_get_qr_code(
                    (user_input.get("user_code") or "").strip()
                )
            except Exception as exc:
                _LOGGER.warning(
                    "Tuya QR request failed (%s)", type(exc).__name__, exc_info=True
                )
                self._qr_token = None
            if self._qr_token:
                return await self.async_step_scan()
            errors["base"] = "login_error"

        return self.async_show_form(
            step_id="cloud",
            data_schema=vol.Schema(
                {
                    vol.Required("user_code"): vol.All(
                        str, vol.Length(min=1, max=128)
                    ),
                }
            ),
            errors=errors,
        )

    def _scan_form(self, errors=None):
        """Build the QR scanner step using Home Assistant's native selector."""
        return self.async_show_form(
            step_id="scan",
            data_schema=vol.Schema(
                {
                    vol.Optional("QR"): QrCodeSelector(
                        config=QrCodeSelectorConfig(
                            data=f"tuyaSmart--qrLogin?token={self._qr_token}",
                            scale=5,
                            error_correction_level=QrErrorCorrectionLevel.QUARTILE,
                        )
                    )
                }
            ),
            errors=errors or {},
        )

    async def async_step_scan(self, user_input=None):
        """Complete QR login, then enumerate account devices and gateways."""
        if user_input is None:
            return self._scan_form()

        if not await self._cloud.async_login():
            self._qr_token = await self._cloud.async_get_qr_code()
            if not self._qr_token:
                return await self.async_step_cloud()
            return self._scan_form({"base": "login_error"})

        try:
            self._cloud_devices = await self._cloud.async_get_devices()
        except Exception as exc:
            _LOGGER.warning(
                "Tuya cloud device discovery failed (%s)",
                type(exc).__name__,
                exc_info=True,
            )
            return self.async_abort(reason="no_devices")

        self._mark_existing_devices()
        return await self.async_step_choose_device()

    async def async_step_choose_device(self, user_input=None):
        """Choose an account device and, when needed, its parent gateway."""
        errors = {}
        if user_input is not None:
            try:
                self._hub_data = resolve_hub_target(
                    self._cloud_devices,
                    user_input["device_id"],
                    user_input["hub_id"],
                )
            except ValueError as exc:
                errors["base"] = str(exc)
            else:
                self._scan_failed = False
                return await self.async_step_search()

        device_options = []
        for key, device in self._cloud_devices.items():
            if device.get("exists") or not device.get("local_key"):
                continue
            label = (
                f"{device['name']} "
                f"({device.get('product_name') or device.get('category') or 'Tuya device'})"
            )
            if not device.get("online"):
                label += " — offline"
            device_options.append(SelectOptionDict(value=key, label=label))

        if not device_options:
            return self.async_abort(reason="no_devices")

        hub_options = [SelectOptionDict(value="None", label="None")]
        for key, device in self._cloud_devices.items():
            if device.get("is_hub"):
                hub_options.append(
                    SelectOptionDict(
                        value=key,
                        label=(
                            f"{device['name']} "
                            f"({device.get('product_name') or 'Tuya gateway'})"
                        ),
                    )
                )

        return self.async_show_form(
            step_id="choose_device",
            data_schema=vol.Schema(
                {
                    vol.Required("device_id"): SelectSelector(
                        SelectSelectorConfig(
                            options=device_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required("hub_id", default="None"): SelectSelector(
                        SelectSelectorConfig(
                            options=hub_options,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_search(self, user_input=None):
        """Search the LAN for the selected parent gateway's current IP."""
        if user_input is None:
            return self.async_show_form(
                step_id="search",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "device_name": self._hub_data.get("device_name", ""),
                },
            )

        def scan_for_device(device_id):
            import tinytuya

            return tinytuya.find_device(dev_id=device_id)

        try:
            discovered = await self.hass.async_add_executor_job(
                scan_for_device, self._hub_data["device_id"]
            )
        except Exception as exc:
            _LOGGER.debug(
                "Tuya LAN discovery failed (%s)", type(exc).__name__, exc_info=True
            )
            discovered = None

        if discovered and discovered.get("ip"):
            self._hub_data["host"] = discovered["ip"]
            detected_version = str(discovered.get("version", ""))
            self._hub_data["protocol_version"] = (
                detected_version
                if detected_version in {str(v) for v in API_PROTOCOL_VERSIONS}
                else "auto"
            )
            self._scan_failed = False
        else:
            self._hub_data["host"] = ""
            self._hub_data.setdefault("protocol_version", "auto")
            self._scan_failed = True

        return await self.async_step_native_hub()

    async def _async_test_connection(
        self,
        device_id: str,
        host: str,
        local_key: str,
        protocol: str,
        node_id: str | None,
    ) -> str:
        """Port Tuya Local's per-protocol fresh-device connection test.

        The original TuyaLocalDevice.async_refresh() retries three times for
        each selected version (six for device22 aliases). A separate
        NativeIRHub per candidate prevents stale TinyTuya handshake state.
        The native DP201/DP202 transport stays owned by IR Studio.
        """
        versions = (
            API_PROTOCOL_VERSIONS if protocol == "auto" else (float(protocol),)
        )
        last_error = None

        for version in versions:
            attempts = 6 if version in (3.22, 3.42, 3.52) else 3
            for attempt in range(attempts):
                hub = NativeIRHub(
                    self.hass,
                    device_id,
                    host,
                    local_key,
                    version,
                    node_id,
                )
                try:
                    await hub.connect()
                    return str(version)
                except Exception as exc:
                    last_error = exc
                    _LOGGER.debug(
                        "Tuya Local-compatible LAN probe failed for protocol %s "
                        "(attempt %s/%s): %s",
                        version,
                        attempt + 1,
                        attempts,
                        type(exc).__name__,
                        exc_info=True,
                    )
                finally:
                    try:
                        await hub.close()
                    except Exception:
                        _LOGGER.debug(
                            "Temporary Tuya LAN connection cleanup failed",
                            exc_info=True,
                        )

        raise ConnectionError(
            "Tuya gateway did not return a valid status on any selected "
            "protocol; see debug log for individual failures"
        ) from last_error

    async def async_step_native_hub(self, user_input=None):
        """Confirm the local parameters and create the physical hub entry."""
        errors = {}
        if user_input is not None:
            device_id = (user_input.get("device_id") or "").strip()
            host = (user_input.get("host") or "").strip()
            local_key = (user_input.get("local_key") or "").strip()
            protocol = str(user_input.get("protocol_version", "auto"))
            node_id = normalize_node_id(
                user_input.get("device_cid") or user_input.get("node_id")
            )

            if not host or not device_id or not local_key:
                errors["base"] = "invalid_credentials"
            else:
                unique_id = (
                    f"native_{device_id}_{node_id}"
                    if node_id
                    else f"native_{device_id}"
                )
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                try:
                    selected_protocol = await self._async_test_connection(
                        device_id,
                        host,
                        local_key,
                        protocol,
                        node_id,
                    )
                except Exception as exc:
                    _LOGGER.warning(
                        "Native Tuya IR hub connection failed (%s)",
                        type(exc).__name__,
                        exc_info=True,
                    )
                    errors["base"] = "cannot_connect"
                else:
                    title = (
                        self._hub_data.get("device_name")
                        or f"Tuya IR Hub ({host})"
                    )
                    return self.async_create_entry(
                        title=title,
                        options={"show_panel": False},
                        data={
                            "kind": "native_hub",
                            "host": host,
                            "device_id": device_id,
                            "local_key": local_key,
                            "protocol_version": selected_protocol,
                            "node_id": node_id,
                        },
                    )

            self._hub_data.update(
                {
                    "device_id": device_id,
                    "host": host,
                    "local_key": local_key,
                    "protocol_version": protocol,
                    "node_id": node_id or "",
                }
            )

        defaults = self._hub_data
        device_id_options = (
            {"default": defaults["device_id"]} if defaults.get("device_id") else {}
        )
        local_key_options = (
            {"default": defaults["local_key"]} if defaults.get("local_key") else {}
        )
        protocol_default = str(defaults.get("protocol_version", "auto"))
        if protocol_default not in {"auto"} | {str(v) for v in API_PROTOCOL_VERSIONS}:
            protocol_default = "auto"

        schema = {
            # Same field names and order as Tuya Local's local-device form.
            vol.Required("device_id", **device_id_options): str,
            vol.Required("host", default=defaults.get("host", "")): str,
            vol.Required("local_key", **local_key_options): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(
                "protocol_version",
                default=protocol_default,
            ): vol.In(["auto"] + [str(v) for v in API_PROTOCOL_VERSIONS]),
        }
        child_id = defaults.get("node_id") or defaults.get("device_cid")
        if child_id:
            schema[vol.Optional("device_cid", default=child_id)] = str
        else:
            schema[vol.Optional("device_cid")] = str

        if self._scan_failed and not errors:
            errors["base"] = "device_not_found"

        return self.async_show_form(
            step_id="native_hub",
            data_schema=vol.Schema(schema),
            errors=errors,
        )
