"""Real HA button entities for remote commands after local save or verification."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from . import _profile_owner_entry_id
from .const import DOMAIN, SIGNAL_CHANGED
from .profile_remote import profile_device_info
from .websocket import _known_code


async def async_setup_entry(hass, entry, async_add_entities):
    runtime = hass.data[DOMAIN]
    if entry.entry_id != _profile_owner_entry_id(hass):
        return
    known = set()
    entities = {}
    watched_sources = set()
    unsub_source = None

    @callback
    def source_changed(event):
        source = event.data.get("entity_id")
        for (profile_id, _button_id), item in entities.items():
            try:
                bound = runtime.find_profile(profile_id)["remote_entity"]
            except ValueError:
                continue
            if bound == source and item.entity_id:
                item.async_write_ha_state()

    @callback
    def update():
        nonlocal watched_sources, unsub_source
        new_entities = []
        valid = {}
        for profile in runtime.profiles:
            for button in profile["buttons"]:
                key = (profile["id"], button["id"])
                if button["status"] not in ("stored", "verified") and not _known_code(hass, profile, button):
                    continue
                valid[key] = True
                if key not in known:
                    known.add(key)
                    item = StudioButton(runtime, profile["id"], button["id"])
                    entities[key] = item
                    new_entities.append(item)
                else:
                    item = entities[key]
                    item.refresh_metadata()
                    if item.entity_id:
                        registry = er.async_get(hass)
                        entity_entry = registry.async_get(item.entity_id)
                        # Original name belongs to the integration. Update it
                        # without changing the entity_id or the user's own name.
                        if (entity_entry is not None and
                                getattr(entity_entry, "original_name", None) != item.name):
                            registry.async_update_entity(
                                item.entity_id, original_name=item.name
                            )
                        item.async_write_ha_state()
        if new_entities:
            async_add_entities(new_entities)
        # Remove only obsolete entities belonging to this integration, never
        # a remote's underlying stored IR code.
        for key in list(entities):
            if key not in valid:
                item = entities.pop(key)
                known.discard(key)
                ent_id = item.entity_id
                if ent_id:
                    reg = er.async_get(hass)
                    if reg.async_get(ent_id):
                        reg.async_remove(ent_id)

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


class StudioButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:remote"

    def __init__(self, runtime, profile_id, button_id):
        self._runtime = runtime
        self._pid = profile_id
        self._bid = button_id
        profile = runtime.find_profile(profile_id)
        button = runtime.find_button(profile, button_id)
        self._attr_name = button["name"]
        self._attr_unique_id = f"{DOMAIN}_{profile_id}_{button_id}"
        self._attr_device_info = profile_device_info(profile)

    @property
    def available(self):
        try:
            profile = self._runtime.find_profile(self._pid)
            button = self._runtime.find_button(profile, self._bid)
        except ValueError:
            return False
        state = self.hass.states.get(profile["remote_entity"])
        return bool(state and state.state in ("on", "off")
                   and not state.attributes.get("ir_studio_virtual")
                   and (button["status"] in ("stored", "verified")
                        or _known_code(self.hass, profile, button)))

    def refresh_metadata(self):
        profile = self._runtime.find_profile(self._pid)
        button = self._runtime.find_button(profile, self._bid)
        self._attr_name = button["name"]
        self._attr_device_info = profile_device_info(profile)

    async def async_press(self):
        profile = self._runtime.find_profile(self._pid)
        button = self._runtime.find_button(profile, self._bid)
        source = self.hass.states.get(profile["remote_entity"])
        if source is None or source.state not in ("on", "off") or source.attributes.get("ir_studio_virtual"):
            raise ValueError("IR transmitter is unavailable or incorrectly bound")
        await self.hass.services.async_call(
            "remote", "send_command",
            {"entity_id": profile["remote_entity"],
             "device": profile.get("remote_device", profile["name"]),
             "command": [button.get("remote_name", button["name"])]},
            blocking=True,
        )
