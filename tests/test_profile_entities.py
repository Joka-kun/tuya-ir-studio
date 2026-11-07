"""Integration-level contract for HA virtual remotes and learned button entities.

Mocks the HA lifecycle, not the device transport: no fake IR codes are produced.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
from enum import IntFlag

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "ir_studio"


@pytest.fixture
def platforms(monkeypatch):
    callbacks = {}
    source_watchers = []
    registered = {}
    removed = []
    calls = []

    homeassistant = types.ModuleType("homeassistant")
    homeassistant.__path__ = []
    components = types.ModuleType("homeassistant.components")
    components.__path__ = []
    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []

    class Entity:
        entity_id = None

        @property
        def name(self):
            return getattr(self, "_attr_name", None)

        @property
        def original_name(self):
            return getattr(self, "_original_name", None)

        @property
        def device_info(self):
            return self._attr_device_info

        def async_write_ha_state(self):
            self._write_count = getattr(self, "_write_count", 0) + 1

    class RemoteEntity(Entity):
        pass

    class ButtonEntity(Entity):
        pass

    class RemoteFeatures(IntFlag):
        LEARN_COMMAND = 1
        DELETE_COMMAND = 2

    remote_mod = types.ModuleType("homeassistant.components.remote")
    remote_mod.RemoteEntity = RemoteEntity
    remote_mod.RemoteEntityFeature = RemoteFeatures
    button_mod = types.ModuleType("homeassistant.components.button")
    button_mod.ButtonEntity = ButtonEntity
    core = types.ModuleType("homeassistant.core")
    core.callback = lambda fn: fn
    device = types.ModuleType("homeassistant.helpers.device_registry")
    device.DeviceInfo = dict
    registered_devices = {}
    device_renames = []

    class DeviceRegistry:
        @property
        def devices(self):
            return {item.id: item for item in registered_devices.values()}

        def async_remove_device(self, device_id):
            # HA removes all entities linked to the deleted virtual device.
            for key, item in list(registered_devices.items()):
                if item.id != device_id:
                    continue
                registered_devices.pop(key)
                for eid, ent in list(registered.items()):
                    if frozenset(ent.device_info["identifiers"]) == key:
                        removed.append(eid)
                        registered.pop(eid)
                break

        def async_get_device(self, *, identifiers):
            return registered_devices.get(frozenset(identifiers))

        def async_update_device(self, device_id, *, name):
            device_renames.append((device_id, name))
            for item in registered_devices.values():
                if item.id == device_id:
                    item.name = name

    device_registry = DeviceRegistry()
    device.async_get = lambda _hass: device_registry
    entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")

    class Registry:
        def async_get(self, eid):
            return registered.get(eid)

        def async_update_entity(self, eid, *, original_name):
            entry = registered[eid]
            entry._original_name = original_name

        def async_remove(self, eid):
            removed.append(eid)
            registered.pop(eid, None)

    registry = Registry()
    entity_registry.async_get = lambda hass: registry

    dispatcher = types.ModuleType("homeassistant.helpers.dispatcher")

    def connect(hass, signal, cb):
        callbacks.setdefault(signal, []).append(cb)

        def unsub():
            callbacks[signal].remove(cb)
        return unsub

    def dispatch(hass, signal):
        for cb in callbacks.get(signal, []):
            cb()

    dispatcher.async_dispatcher_connect = connect
    dispatcher.async_dispatcher_send = dispatch
    event = types.ModuleType("homeassistant.helpers.event")

    def async_track_state_change_event(_hass, entity_ids, callback):
        record = (set(entity_ids), callback)
        source_watchers.append(record)

        def remove():
            if record in source_watchers:
                source_watchers.remove(record)
        return remove

    event.async_track_state_change_event = async_track_state_change_event
    storage = types.ModuleType("homeassistant.helpers.storage")

    class Store:
        def __init__(self, *_args):
            pass

        async def async_load(self):
            return {}

    storage.Store = Store

    for mod in (
        homeassistant, components, helpers, remote_mod, button_mod, core, device,
        entity_registry, dispatcher, event, storage,
    ):
        monkeypatch.setitem(sys.modules, mod.__name__, mod)

    package = types.ModuleType("ir_studio")
    package.__path__ = [str(ROOT)]
    package._profile_owner_entry_id = lambda hass: "owner"
    monkeypatch.setitem(sys.modules, "ir_studio", package)

    websocket = types.ModuleType("ir_studio.websocket")
    websocket._known_code = lambda _hass, _profile, button: button.get("code_exists", False)
    monkeypatch.setitem(sys.modules, "ir_studio.websocket", websocket)
    native = types.ModuleType("ir_studio.native_transport")
    native.validate_code = lambda code: code
    monkeypatch.setitem(sys.modules, "ir_studio.native_transport", native)

    modules = {}
    for name in ("profile_remote", "button", "remote"):
        spec = importlib.util.spec_from_file_location(
            "ir_studio." + name, ROOT / (name + ".py")
        )
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, "ir_studio." + name, module)
        spec.loader.exec_module(module)
        modules[name] = module

    profile = {
        "id": "p_unchanging_uuid", "name": "Table lamp",
        "remote_entity": "remote.physical_ir", "remote_device": "original",
        "icon": "lamp",
        "buttons": [{
            "id": "b_stable_uuid", "name": "Power", "remote_name": "Power",
            "status": "stored", "verified": False,
        }],
    }

    class Runtime:
        profiles = [profile]
        icons = [{"id": "lamp", "mdi": "chandelier"}]
        native_hubs = {}
        native_remotes = {}

        def find_profile(self, pid):
            for item in self.profiles:
                if item["id"] == pid:
                    return item
            raise ValueError("Not found")

        def find_button(self, profile, bid):
            for item in profile["buttons"]:
                if item["id"] == bid:
                    return item
            raise ValueError("Not found")

    runtime = Runtime()
    states = {
        "remote.physical_ir": types.SimpleNamespace(state="off", attributes={})
    }

    async def service_call(domain, service, data, blocking=False):
        calls.append((domain, service, data, blocking))

    hass = types.SimpleNamespace(
        data={"ir_studio": runtime},
        states=states,
        services=types.SimpleNamespace(async_call=service_call),
    )

    class Entry:
        def __init__(self, entry_id):
            self.entry_id = entry_id
            self.data = {"kind": "manager"}
            self.callbacks = []

        def async_on_unload(self, callback):
            self.callbacks.append(callback)

    added = []

    def async_add_entities(entities):
        for entity in entities:
            entity.hass = hass
            entity.entity_id = ("remote." if isinstance(entity, RemoteEntity)
                                else "button.") + entity.unique_id
            registered[entity.entity_id] = entity
            info = entity.device_info
            key = frozenset(info["identifiers"])
            if key not in registered_devices:
                registered_devices[key] = types.SimpleNamespace(
                    id="test_device_" + str(len(registered_devices) + 1),
                    name=info["name"],
                    model=info["model"],
                    identifiers=key,
                )
            added.append(entity)

    # The stubs emulate Home Assistant registry recognition of unique IDs.
    Entity.unique_id = property(lambda self: self._attr_unique_id)

    return types.SimpleNamespace(
        modules=modules, hass=hass, runtime=runtime, profile=profile,
        Entry=Entry, add=async_add_entities, added=added, calls=calls,
        removed=removed, dispatch=dispatch, source_watchers=source_watchers,
        registered_devices=registered_devices, device_renames=device_renames,
    )


@pytest.mark.asyncio
async def test_manager_exposes_virtual_profile_remote_and_learned_button(platforms):
    p = platforms
    owner = p.Entry("owner")
    await p.modules["remote"].async_setup_entry(p.hass, owner, p.add)
    await p.modules["button"].async_setup_entry(p.hass, owner, p.add)

    remote = next(item for item in p.added
                  if isinstance(item, p.modules["profile_remote"].StudioProfileRemote))
    button = next(item for item in p.added
                  if isinstance(item, p.modules["button"].StudioButton))
    assert remote.unique_id == "ir_studio_profile_p_unchanging_uuid"
    assert button.unique_id == "ir_studio_p_unchanging_uuid_b_stable_uuid"
    assert remote.device_info["identifiers"] == button.device_info["identifiers"]
    assert remote.device_info["name"] == "Table lamp"
    assert remote.extra_state_attributes["ir_studio_virtual"] is True
    assert remote.available is True  # 'off' = normal IR gateway idle state
    assert button.available is True
    await remote.async_send_command(["Power"])
    await button.async_press()
    assert len(p.calls) == 2
    assert all(call[0:2] == ("remote", "send_command") for call in p.calls)
    assert all(call[2] == {"entity_id": "remote.physical_ir",
                           "device": "original", "command": ["Power"]}
               for call in p.calls)
    assert all(call[3] is True for call in p.calls)


@pytest.mark.asyncio
async def test_only_owner_registers_and_lifecycle_adds_or_removes_entities(platforms):
    p = platforms
    other = p.Entry("another_hub")
    await p.modules["remote"].async_setup_entry(p.hass, other, p.add)
    await p.modules["button"].async_setup_entry(p.hass, other, p.add)
    assert p.added == []
    owner = p.Entry("owner")
    await p.modules["remote"].async_setup_entry(p.hass, owner, p.add)
    await p.modules["button"].async_setup_entry(p.hass, owner, p.add)
    assert len(p.added) == 2

    # Pending (no known code) commands must not create inert HA buttons.
    pending = {"id": "b2", "name": "Mute", "remote_name": "Mute",
               "status": "pending", "verified": False}
    p.profile["buttons"].append(pending)
    p.dispatch(p.hass, "ir_studio_profiles_changed")
    assert len(p.added) == 2
    pending["status"] = "stored"
    p.dispatch(p.hass, "ir_studio_profiles_changed")
    assert len(p.added) == 3
    assert p.added[-1].unique_id == "ir_studio_p_unchanging_uuid_b2"

    # Profile deletion removes its HA entities but does not write IR stores.
    p.runtime.profiles = []
    p.dispatch(p.hass, "ir_studio_profiles_changed")
    assert len(p.removed) == 3


@pytest.mark.asyncio
async def test_virtual_ir_transmitter_recursion_blocked(platforms):
    p = platforms
    owner = p.Entry("owner")
    await p.modules["remote"].async_setup_entry(p.hass, owner, p.add)
    remote = p.added[0]
    p.hass.states["remote.physical_ir"] = types.SimpleNamespace(
        state="on", attributes={"ir_studio_virtual": True}
    )
    assert remote.available is False
    with pytest.raises(ValueError, match="physical transmitter"):
        await remote.async_send_command("Power")
    assert not p.calls


def test_catalog_and_platform_setup_are_nonblocking_and_cover_native_hubs():
    src = (ROOT / "__init__.py").read_text(encoding="utf-8")
    assert 'await self.hass.async_add_executor_job(' in src
    assert '_read_static_catalog, "icon_catalog.json"' in src
    assert '_read_static_catalog, "presets.json"' in src
    assert '["remote", "button"]' in src
    assert 'platforms = ["remote", "button"]' in src
    # Avoid regression: new hubs must not be constrained to remote only.
    assert 'async_forward_entry_setups(entry, ["remote"])' not in src


@pytest.mark.asyncio
async def test_physical_gateway_state_changes_refresh_virtual_entities(platforms):
    p = platforms
    owner = p.Entry("owner")
    await p.modules["remote"].async_setup_entry(p.hass, owner, p.add)
    await p.modules["button"].async_setup_entry(p.hass, owner, p.add)
    assert len(p.source_watchers) == 2
    entities = p.added[:]
    counts = [getattr(e, "_write_count", 0) for e in entities]
    p.hass.states["remote.physical_ir"].state = "unavailable"
    event = types.SimpleNamespace(data={"entity_id": "remote.physical_ir"})
    for _sources, cb in p.source_watchers[:]:
        cb(event)
    assert all(getattr(e, "_write_count", 0) > before
               for e, before in zip(entities, counts))
    assert all(e.available is False for e in entities)
    p.hass.states["remote.physical_ir"].state = "off"
    for _sources, cb in p.source_watchers[:]:
        cb(event)
    assert all(e.available is True for e in entities)

    for unsub in owner.callbacks:
        unsub()
    assert not p.source_watchers


@pytest.mark.asyncio
async def test_profile_rename_updates_ha_device_name_without_changing_unique_ids(platforms):
    p = platforms
    owner = p.Entry("owner")
    await p.modules["remote"].async_setup_entry(p.hass, owner, p.add)
    await p.modules["button"].async_setup_entry(p.hass, owner, p.add)
    ids = [entity.unique_id for entity in p.added]
    p.profile["name"] = "Bedroom lamp"
    p.dispatch(p.hass, "ir_studio_profiles_changed")
    assert len(p.registered_devices) == 1
    assert next(iter(p.registered_devices.values())).name == "Bedroom lamp"
    assert p.device_renames == [("test_device_1", "Bedroom lamp")]
    assert [entity.unique_id for entity in p.added] == ids


def test_profile_entity_owner_skips_offline_hubs_and_sticks_until_unloaded():
    import ast
    src = ast.parse((ROOT / "__init__.py").read_text(encoding="utf-8"))
    fn = next(n for n in src.body
              if isinstance(n, ast.FunctionDef)
              and n.name == "_profile_owner_entry_id")
    compiled = compile(ast.Module(body=[fn], type_ignores=[]), "<owner>", "exec")
    namespace = {"DOMAIN": "ir_studio"}
    exec(compiled, namespace)
    choose = namespace["_profile_owner_entry_id"]

    class Entries:
        def __init__(self, entries):
            self.entries = entries

        def async_entries(self, _domain):
            return self.entries

    def entry(entry_id, kind, state, disabled_by=None):
        return types.SimpleNamespace(
            entry_id=entry_id, data={"kind": kind},
            state=types.SimpleNamespace(value=state),
            disabled_by=disabled_by,
        )

    e = [
        entry("aa_offline", "native_hub", "setup_retry"),
        entry("bb_active", "native_hub", "setup_in_progress"),
        entry("cc_manager", "manager", "not_loaded"),
    ]
    runtime = types.SimpleNamespace(profile_owner_entry_id=None)
    hass = types.SimpleNamespace(
        data={"ir_studio": runtime},
        config_entries=Entries(e),
    )
    assert choose(hass) == "bb_active"
    assert runtime.profile_owner_entry_id == "bb_active"
    e[2].state.value = "loaded"
    assert choose(hass) == "bb_active"  # No duplicate owner after late setup.
    e[1].state.value = "unload_in_progress"
    assert choose(hass) == "cc_manager"
    assert runtime.profile_owner_entry_id == "cc_manager"


@pytest.mark.asyncio
async def test_deleting_profile_removes_virtual_device_but_preserves_physical_gateway(platforms):
    p = platforms
    owner = p.Entry("owner")
    await p.modules["remote"].async_setup_entry(p.hass, owner, p.add)
    await p.modules["button"].async_setup_entry(p.hass, owner, p.add)
    key = frozenset({("ir_studio", p.profile["id"])})
    assert key in p.registered_devices

    # A physical gateway is not an IR Studio virtual appliance.
    hub_key = frozenset({("ir_studio", "native_hub_test")})
    p.registered_devices[hub_key] = types.SimpleNamespace(
        id="physical_hub", name="Bedroom hub", identifiers=hub_key,
        model="Tuya IR hub (LAN)",
    )
    p.runtime.profiles = []
    p.dispatch(p.hass, "ir_studio_profiles_changed")
    assert key not in p.registered_devices
    assert hub_key in p.registered_devices
    assert len(p.removed) == 2


@pytest.mark.asyncio
async def test_stale_old_virtual_device_pruned_after_restart(platforms):
    p = platforms
    old_key = frozenset({("ir_studio", "removed_before_update")})
    p.registered_devices[old_key] = types.SimpleNamespace(
        id="old_ha_device", name="Obsolete lamp",
        identifiers=old_key, model="Virtual infrared remote",
    )
    live_key = frozenset({("ir_studio", p.profile["id"])})
    owner = p.Entry("owner")
    await p.modules["remote"].async_setup_entry(p.hass, owner, p.add)
    assert old_key not in p.registered_devices
    assert live_key in p.registered_devices
    assert not p.removed


@pytest.mark.asyncio
async def test_button_rename_updates_entity_original_name_but_keeps_unique_id(platforms):
    p = platforms
    owner = p.Entry("owner")
    await p.modules["remote"].async_setup_entry(p.hass, owner, p.add)
    await p.modules["button"].async_setup_entry(p.hass, owner, p.add)
    button = next(x for x in p.added
                  if isinstance(x, p.modules["button"].StudioButton))
    before = button.unique_id
    # A user-customized HA entity name must not be overwritten by integration.
    button._custom_name_by_user = "My HA override"
    p.profile["buttons"][0]["name"] = "Power TV"
    p.dispatch(p.hass, "ir_studio_profiles_changed")
    assert button.name == "Power TV"
    assert button.original_name == "Power TV"
    assert button.unique_id == before
    assert p.profile["buttons"][0]["remote_name"] == "Power"
    assert button._custom_name_by_user == "My HA override"
