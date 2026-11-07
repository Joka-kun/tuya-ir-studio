"""Virtual Home Assistant remotes backed by IR Studio's learned profile commands.

A virtual remote is an independent HA device, not another physical transmitter.
Only the selected underlying HA remote talks to the actual IR gateway.
"""
from __future__ import annotations

from homeassistant.components.remote import RemoteEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN


def profile_device_info(profile):
    return DeviceInfo(
        identifiers={(DOMAIN, profile["id"])},
        name=profile["name"],
        manufacturer="IR Studio",
        model="Virtual infrared remote",
    )


class StudioProfileRemote(RemoteEntity):
    """One stable remote entity per IR Studio profile."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_is_on = True
    _attr_should_poll = False

    def __init__(self, runtime, profile_id):
        self._runtime = runtime
        self._profile_id = profile_id
        self._attr_unique_id = f"{DOMAIN}_profile_{profile_id}"
        self.refresh_metadata()

    def _profile(self):
        return self._runtime.find_profile(self._profile_id)

    def refresh_metadata(self):
        profile = self._profile()
        self._attr_device_info = profile_device_info(profile)
        icons = {item["id"]: item["mdi"] for item in self._runtime.icons}
        self._attr_icon = profile.get("icon_mdi") or ("mdi:" + icons.get(profile.get("icon"), "remote"))

    @property
    def available(self):
        try:
            profile = self._profile()
        except ValueError:
            return False
        # The underlying Remote can be 'off' when its IR receiver is idle.
        source = self.hass.states.get(profile["remote_entity"])
        return bool(source and source.state in ("on", "off")
                    and not getattr(source, "attributes", {}).get("ir_studio_virtual")
                    and profile["remote_entity"] != self.entity_id)

    @property
    def extra_state_attributes(self):
        # Frontend selection and WebSocket binding guards detect virtual remotes.
        return {
            "ir_studio_virtual": True,
            "ir_studio_profile_id": self._profile_id,
        }

    async def async_send_command(self, command, **kwargs):
        profile = self._profile()
        upstream = profile["remote_entity"]
        source = self.hass.states.get(upstream)
        if (upstream == self.entity_id or source is None
                or source.state not in ("on", "off")
                or getattr(source, "attributes", {}).get("ir_studio_virtual")):
            raise ValueError("Virtual IR remote requires an available physical transmitter")

        device = profile.get("remote_device", profile["name"])
        if kwargs.get("device") not in (None, device):
            raise ValueError("IR command targets a different device namespace")
        names = [command] if isinstance(command, str) else command
        if not isinstance(names, (list, tuple)) or not names:
            raise ValueError("Select at least one remote command")
        mapping = {}
        for button in profile.get("buttons", []):
            # Do not synthesize waveforms: only expose declared command keys.
            key = button.get("remote_name", button.get("name"))
            mapping[key] = key
            mapping[button["name"]] = key
        if any(not isinstance(name, str) or name not in mapping for name in names):
            raise ValueError("Unknown IR Studio command for this remote")
        data = {
            "entity_id": upstream,
            "device": device,
            "command": [mapping[name] for name in names],
        }
        for field in ("num_repeats", "delay_secs"):
            if field in kwargs:
                data[field] = kwargs[field]
        await self.hass.services.async_call(
            "remote", "send_command", data, blocking=True
        )

    async def async_turn_on(self, **kwargs):
        # This is a logical HA remote state, not the appliance power button.
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._attr_is_on = False
        self.async_write_ha_state()
