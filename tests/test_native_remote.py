"""Home Assistant RemoteEntity contract tests for the native Tuya adapter."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import types
from enum import IntFlag

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "ir_studio"


@pytest.fixture
def remote_module(monkeypatch):
    homeassistant = types.ModuleType("homeassistant")
    homeassistant.__path__ = []
    components = types.ModuleType("homeassistant.components")
    components.__path__ = []
    remote_api = types.ModuleType("homeassistant.components.remote")

    class Features(IntFlag):
        LEARN_COMMAND = 1
        DELETE_COMMAND = 2

    class RemoteEntity:
        async def async_added_to_hass(self):
            return None

        async def async_will_remove_from_hass(self):
            return None

        def async_write_ha_state(self):
            return None

    remote_api.RemoteEntity = RemoteEntity
    remote_api.RemoteEntityFeature = Features

    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    device_registry.DeviceInfo = dict
    storage = types.ModuleType("homeassistant.helpers.storage")

    class FakeStore:
        def __init__(self, *_args):
            self.data = None

        async def async_load(self):
            return copy.deepcopy(self.data)

        async def async_save(self, data):
            self.data = copy.deepcopy(data)

    storage.Store = FakeStore
    core = types.ModuleType("homeassistant.core")
    core.callback = lambda fn: fn
    entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
    entity_registry.async_get = lambda _hass: None
    dispatcher = types.ModuleType("homeassistant.helpers.dispatcher")
    dispatcher.async_dispatcher_connect = lambda _hass, _signal, _cb: (lambda: None)
    dispatcher.async_dispatcher_send = lambda *_args: None
    event = types.ModuleType("homeassistant.helpers.event")
    event.async_track_state_change_event = lambda _hass, _ids, _cb: (lambda: None)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.event", event)
    monkeypatch.setitem(sys.modules, "homeassistant.core", core)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.entity_registry", entity_registry)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.dispatcher", dispatcher)
    virtual = types.ModuleType("ir_studio.profile_remote")
    virtual.StudioProfileRemote = type("StudioProfileRemote", (), {})
    monkeypatch.setitem(sys.modules, "ir_studio.profile_remote", virtual)
    monkeypatch.setitem(sys.modules, "homeassistant", homeassistant)
    monkeypatch.setitem(sys.modules, "homeassistant.components", components)
    monkeypatch.setitem(sys.modules, "homeassistant.components.remote", remote_api)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers", helpers)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.device_registry", device_registry)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.storage", storage)

    package = sys.modules.get("ir_studio")
    if package is None:
        package = types.ModuleType("ir_studio")
        package.__path__ = [str(ROOT)]
        monkeypatch.setitem(sys.modules, "ir_studio", package)
    else:
        package.__path__ = [str(ROOT)]
    package._profile_owner_entry_id = lambda _hass: "none"

    spec = importlib.util.spec_from_file_location(
        "ir_studio.remote", ROOT / "remote.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "ir_studio.remote", module)
    spec.loader.exec_module(module)
    return module


class AsyncLock:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


class Runtime:
    def __init__(self):
        self.hass = types.SimpleNamespace()
        self.lock = AsyncLock()
        self.native_codes = {"profile/button": "IMPORTED"}
        self.profiles = [
            {
                "id": "profile",
                "name": "Living room",
                "remote_entity": "remote.test",
                "remote_device": "TV",
                "buttons": [
                    {
                        "id": "button",
                        "name": "Power",
                        "remote_name": "Power",
                        "status": "stored",
                        "verified": False,
                    }
                ],
            }
        ]
        self.native_remotes = {}
        self.saves = 0

    async def save(self):
        self.saves += 1


class Hub:
    available = True

    def __init__(self):
        self.sent = []

    async def send(self, code, delay_ms=0):
        self.sent.append((code, delay_ms))

    async def learn(self, _timeout):
        return "LEARNED"


@pytest.fixture
def entity(remote_module):
    runtime = Runtime()
    entry = types.SimpleNamespace(entry_id="entry", title="Tuya IR Hub")
    hub = Hub()
    item = remote_module.NativeIRRemote(runtime, entry, hub)
    item.entity_id = "remote.test"
    return runtime, hub, item


@pytest.mark.asyncio
async def test_send_command_resolves_single_device_when_device_is_omitted(entity):
    _runtime, hub, item = entity
    item._codes = {"TV": {"Power": "LEARNED"}}
    await item.async_send_command(["Power"])
    assert hub.sent == [("LEARNED", 400)]


@pytest.mark.asyncio
async def test_send_command_requires_device_when_multiple_namespaces_exist(entity):
    _runtime, _hub, item = entity
    item._codes = {"TV": {"Power": "A"}, "Fan": {"Power": "B"}}
    with pytest.raises(ValueError, match="multiple devices"):
        await item.async_send_command(["Power"])


@pytest.mark.asyncio
async def test_delete_command_removes_learned_and_imported_codes(entity):
    runtime, _hub, item = entity
    item._codes = {"TV": {"Power": "LEARNED", "Mute": "MUTE"}}
    await item.async_delete_command(command=["Power"], device="TV")

    assert item._codes == {"TV": {"Mute": "MUTE"}}
    assert "profile/button" not in runtime.native_codes
    assert runtime.profiles[0]["buttons"][0]["status"] == "pending"
    assert runtime.saves == 1


@pytest.mark.asyncio
async def test_delete_command_can_remove_imported_code_without_local_learned_store(entity):
    runtime, _hub, item = entity
    await item.async_delete_command(command=["Power"], device="TV")
    assert not runtime.native_codes
    assert runtime.profiles[0]["buttons"][0]["verified"] is False
    assert runtime.saves == 1


def test_remote_send_is_base_operation_not_a_feature_flag(remote_module):
    flags = remote_module.NativeIRRemote._attr_supported_features
    assert flags == (
        remote_module.RemoteEntityFeature.LEARN_COMMAND
        | remote_module.RemoteEntityFeature.DELETE_COMMAND
    )


@pytest.mark.asyncio
async def test_delete_learned_code_resets_profile_button_status(entity):
    runtime, _hub, item = entity
    runtime.native_codes = {}
    item._codes = {"TV": {"Power": "LEARNED"}}
    await item.async_delete_command(command=["Power"], device="TV")
    assert item._codes == {}
    assert runtime.profiles[0]["buttons"][0]["status"] == "pending"
    assert runtime.saves == 1



@pytest.mark.asyncio
async def test_native_learn_persists_code_and_can_send_it_after_reload(entity):
    """Prove code is retained by the entity's HA Store, not just in memory."""
    _runtime, hub, item = entity
    await item.async_learn_command(device="TV", command=["Power"], timeout=30)
    assert item._codes["TV"]["Power"] == "LEARNED"
    assert item._store.data["TV"]["Power"] == "LEARNED"

    # A later entity instance reading the same HA Store has its own fresh
    # in-memory cache, but the stored DP202 code remains available.
    item._codes = {}
    await item.async_load_codes()
    assert item.has_code("TV", "Power")
    await item.async_send_command(["Power"], device="TV")
    assert hub.sent == [("LEARNED", 400)]
