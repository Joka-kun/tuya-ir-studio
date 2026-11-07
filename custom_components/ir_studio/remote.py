"""Native direct-LAN Tuya IR remote platform for IR Studio."""
from __future__ import annotations

import asyncio
import copy
from collections.abc import Iterable

from homeassistant.components.remote import RemoteEntity, RemoteEntityFeature
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store

from . import _profile_owner_entry_id
from .const import DOMAIN, SIGNAL_CHANGED
from .native_transport import validate_code
from .profile_remote import StudioProfileRemote


def _commands(value):
    if isinstance(value, str):
        return [value]
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("At least one IR command required")
    if not all(isinstance(command, str) and command for command in value):
        raise ValueError("Invalid IR command")
    return list(value)


@callback
def _prune_deleted_virtual_devices(hass, active_profile_ids: set[str]) -> None:
    """Remove *only* orphaned IR Studio virtual Devices from HA's registry.

    Removing a remote entity alone leaves an empty device in Home Assistant.
    The registry also persists across restarts, so scan all known IR Studio
    virtual devices, not just the objects tracked in the current session.
    Home Assistant removes their associated entity-registry entries when the
    device itself is removed. Never touch the physical IR hub device.
    """
    registry = dr.async_get(hass)
    for device in tuple(registry.devices.values()):
        if device.model not in ("Virtual infrared remote", "Local IR virtual remote"):
            continue
        identifiers = {
            identifier for domain, identifier in device.identifiers
            if domain == DOMAIN
        }
        if identifiers and not (identifiers & active_profile_ids):
            registry.async_remove_device(device.id)


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = hass.data[DOMAIN]
    hub = runtime.native_hubs.get(entry.entry_id)
    if hub is not None:
        device = NativeIRRemote(runtime, entry, hub)
        await device.async_load_codes()
        async_add_entities([device])

    if entry.entry_id != _profile_owner_entry_id(hass):
        return

    # Exactly one entry owns virtual remotes even with multiple IR hubs.
    profiles = {}
    watched_sources = set()
    unsub_source = None

    @callback
    def source_changed(event):
        entity_id = event.data.get("entity_id")
        for pid, entity in profiles.items():
            try:
                bound = runtime.find_profile(pid)["remote_entity"]
            except ValueError:
                continue
            if entity.entity_id and bound == entity_id:
                entity.async_write_ha_state()

    @callback
    def update():
        nonlocal watched_sources, unsub_source
        current = set()
        new = []
        for profile in runtime.profiles:
            pid = profile["id"]
            current.add(pid)
            item = profiles.get(pid)
            if item is None:
                item = StudioProfileRemote(runtime, pid)
                profiles[pid] = item
                new.append(item)
            else:
                item.refresh_metadata()
                # DeviceInfo is only applied at first registry registration.
                # Keep generated HA device names in sync with profile renames,
                # while preserving the user's name_by_user override.
                device_registry = dr.async_get(hass)
                device_entry = device_registry.async_get_device(
                    identifiers={(DOMAIN, pid)}
                )
                if device_entry and device_entry.name != profile["name"]:
                    device_registry.async_update_device(
                        device_entry.id, name=profile["name"]
                    )
                if item.entity_id:
                    item.async_write_ha_state()
        if new:
            async_add_entities(new)
        for pid in set(profiles) - current:
            item = profiles.pop(pid)
            if item.entity_id:
                registry = er.async_get(hass)
                if registry.async_get(item.entity_id):
                    registry.async_remove(item.entity_id)

        # Also catch orphaned devices that were deleted by an older release,
        # while HA was offline, or before the entity platform subscribed.
        _prune_deleted_virtual_devices(hass, current)

        sources = {profile["remote_entity"] for profile in runtime.profiles}
        if sources != watched_sources:
            if unsub_source:
                unsub_source()
            watched_sources = sources
            unsub_source = (
                async_track_state_change_event(hass, list(sources), source_changed)
                if sources else None
            )

    update()
    entry.async_on_unload(async_dispatcher_connect(hass, SIGNAL_CHANGED, update))
    entry.async_on_unload(lambda: unsub_source() if unsub_source else None)


class NativeIRRemote(RemoteEntity):
    _attr_has_entity_name = True
    _attr_name = "IR transmitter"
    _attr_icon = "mdi:remote"
    _attr_is_on = True
    # send_command is the base RemoteEntity operation and has no feature flag.
    _attr_supported_features = (
        RemoteEntityFeature.LEARN_COMMAND | RemoteEntityFeature.DELETE_COMMAND
    )

    def __init__(self, runtime, entry, hub):
        self._runtime = runtime
        self._entry = entry
        self._hub = hub
        self._attr_unique_id = f"{DOMAIN}_native_{entry.entry_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"native_{entry.entry_id}")},
            name=entry.title,
            manufacturer="Tuya",
            model="Tuya IR hub (LAN)",
        )
        self._store = Store(runtime.hass, 1, f"ir_studio_native_codes_{entry.entry_id}")
        self._codes: dict[str, dict[str, str]] = {}
        self._code_lock = asyncio.Lock()

    @property
    def available(self):
        return self._hub.available

    async def async_load_codes(self):
        self._codes = await self._store.async_load() or {}

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._runtime.native_remotes[self.entity_id] = self
        async_dispatcher_send(self._runtime.hass, SIGNAL_CHANGED)

    async def async_will_remove_from_hass(self):
        if self._runtime.native_remotes.get(self.entity_id) is self:
            self._runtime.native_remotes.pop(self.entity_id, None)
        await super().async_will_remove_from_hass()

    def get_code(self, device, command):
        return self._codes.get(device, {}).get(command)

    def _imported_code(self, device, command):
        for profile in self._runtime.profiles:
            if profile.get("remote_entity") != self.entity_id:
                continue
            if profile.get("remote_device", profile.get("name")) != device:
                continue
            for button in profile.get("buttons", []):
                if button.get("remote_name", button.get("name")) != command:
                    continue
                return self._runtime.native_codes.get(
                    f"{profile.get('id')}/{button.get('id')}"
                )
        return None

    def _known_devices(self):
        devices = set(self._codes)
        for profile in self._runtime.profiles:
            if profile.get("remote_entity") != self.entity_id:
                continue
            device = profile.get("remote_device", profile.get("name"))
            if not device:
                continue
            if any(
                self._runtime.native_codes.get(
                    f"{profile.get('id')}/{button.get('id')}"
                )
                for button in profile.get("buttons", [])
            ):
                devices.add(device)
        return devices

    def _resolve_device(self, value):
        if value is not None:
            if not isinstance(value, str) or not value:
                raise ValueError("Invalid device namespace")
            return value
        devices = self._known_devices()
        if len(devices) == 1:
            return next(iter(devices))
        if not devices:
            raise ValueError("The device namespace is required")
        raise ValueError("Specify device when this remote has multiple devices")

    def has_code(self, device, command):
        return (
            self.get_code(device, command) is not None
            or self._imported_code(device, command) is not None
        )

    async def async_send_command(self, command: Iterable[str], **kwargs):
        device = self._resolve_device(kwargs.get("device"))
        repeats = kwargs.get("num_repeats", 1)
        if type(repeats) is not int or not 1 <= repeats <= 10:
            raise ValueError("Invalid repeat count")
        delay = kwargs.get("delay_secs", 0.4)
        if isinstance(delay, bool) or not isinstance(delay, (int, float)):
            raise ValueError("Invalid delay")
        if not 0 <= delay <= 10:
            raise ValueError("Invalid delay")

        names = _commands(command)
        async with self._runtime.lock:
            async with self._code_lock:
                device = self._resolve_device(kwargs.get("device"))
                codes = []
                for name in names:
                    code = self.get_code(device, name) or self._imported_code(device, name)
                    if not code:
                        raise ValueError("IR command not learned for selected device")
                    codes.append(validate_code(code))

        sent = False
        for _ in range(repeats):
            for code in codes:
                if sent and delay:
                    await asyncio.sleep(delay)
                await self._hub.send(code, delay_ms=int(delay * 1000))
                sent = True
        self.async_write_ha_state()

    async def async_learn_command(self, **kwargs):
        device = kwargs.get("device") or "default"
        if not isinstance(device, str) or not device:
            raise ValueError("Invalid device namespace")
        timeout = kwargs.get("timeout", 30)
        if type(timeout) is not int or not 10 <= timeout <= 90:
            timeout = 30

        async with self._code_lock:
            new_codes = copy.deepcopy(self._codes)
            for name in _commands(kwargs.get("command", [])):
                code = await self._hub.learn(timeout)
                new_codes.setdefault(device, {})[name] = validate_code(code)
            await self._store.async_save(new_codes)
            self._codes = new_codes
        async with self._runtime.lock:
            await self._runtime.save()
        self.async_write_ha_state()

    async def async_delete_command(self, **kwargs):
        device = kwargs.get("device")
        if device is not None and (not isinstance(device, str) or not device):
            raise ValueError("Invalid device namespace")
        names = set(_commands(kwargs.get("command", [])))

        async with self._runtime.lock:
            async with self._code_lock:
                new_codes = copy.deepcopy(self._codes)
                targets = [device] if device is not None else list(new_codes)
                removed_local = False
                removed_local_commands = set()
                for namespace in targets:
                    stored = new_codes.get(namespace)
                    if not stored:
                        continue
                    for name in names:
                        if name in stored:
                            stored.pop(name)
                            removed_local = True
                            removed_local_commands.add((namespace, name))
                    if not stored:
                        new_codes.pop(namespace, None)
    
                new_imported = dict(self._runtime.native_codes)
                removed_imported = False
                changed_profiles = []
                for profile in self._runtime.profiles:
                    if profile.get("remote_entity") != self.entity_id:
                        continue
                    profile_device = profile.get("remote_device", profile.get("name"))
                    if device is not None and profile_device != device:
                        continue
                    for button in profile.get("buttons", []):
                        command_name = button.get("remote_name", button.get("name"))
                        key = f"{profile.get('id')}/{button.get('id')}"
                        imported_removed = command_name in names and key in new_imported
                        learned_removed = (profile_device, command_name) in removed_local_commands
                        if imported_removed:
                            new_imported.pop(key, None)
                            removed_imported = True
                        if imported_removed or learned_removed:
                            changed_profiles.append(button)
    
                if not removed_local and not removed_imported:
                    raise ValueError("No learned commands found for the selected device")
    
                if removed_local:
                    await self._store.async_save(new_codes)
                    self._codes = new_codes
                if removed_imported:
                    self._runtime.native_codes = new_imported
                for button in changed_profiles:
                    button["status"] = "pending"
                    button["verified"] = False
    
            await self._runtime.save()
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        # Logical HA Remote state; this does not turn on the appliance.
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._attr_is_on = False
        self.async_write_ha_state()
