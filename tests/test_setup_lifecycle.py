"""Config-entry setup cleanup tests with a minimal Home Assistant host."""
from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "ir_studio"


@pytest.mark.asyncio
async def test_native_setup_failure_runs_registered_cleanup(monkeypatch):
    removed_panels = []
    registered_panels = []
    registered_paths = []

    homeassistant = types.ModuleType("homeassistant")
    homeassistant.__path__ = []
    components = types.ModuleType("homeassistant.components")
    components.__path__ = []

    frontend = types.ModuleType("homeassistant.components.frontend")
    frontend.async_remove_panel = lambda hass, path: removed_panels.append(path)

    panel_custom = types.ModuleType("homeassistant.components.panel_custom")

    async def register_panel(**kwargs):
        registered_panels.append(kwargs["frontend_url_path"])

    panel_custom.async_register_panel = register_panel
    websocket_api = types.ModuleType("homeassistant.components.websocket_api")
    websocket_api.websocket_command = lambda _schema: (lambda fn: fn)
    websocket_api.require_admin = lambda fn: fn
    websocket_api.async_response = lambda fn: fn
    websocket_api.async_register_command = lambda *_args: None
    components.frontend = frontend
    components.panel_custom = panel_custom
    components.websocket_api = websocket_api

    http_module = types.ModuleType("homeassistant.components.http")

    class StaticPathConfig:
        def __init__(self, *args):
            self.args = args

    http_module.StaticPathConfig = StaticPathConfig

    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = type("HomeAssistant", (), {})
    core.Context = lambda **kwargs: kwargs
    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    dispatcher = types.ModuleType("homeassistant.helpers.dispatcher")
    dispatcher.async_dispatcher_send = lambda *_args: None
    entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
    entity_registry.async_get = lambda _hass: types.SimpleNamespace(async_get=lambda _entity: None)
    helpers.entity_registry = entity_registry
    storage = types.ModuleType("homeassistant.helpers.storage")

    class FakeStore:
        def __init__(self, *_args):
            pass

        async def async_load(self):
            return {}

        async def async_save(self, _data):
            return None

    storage.Store = FakeStore

    exceptions = types.ModuleType("homeassistant.exceptions")

    class ConfigEntryNotReady(Exception):
        pass

    exceptions.ConfigEntryNotReady = ConfigEntryNotReady

    for name, module in {
        "homeassistant": homeassistant,
        "homeassistant.components": components,
        "homeassistant.components.frontend": frontend,
        "homeassistant.components.panel_custom": panel_custom,
        "homeassistant.components.websocket_api": websocket_api,
        "homeassistant.components.http": http_module,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.dispatcher": dispatcher,
        "homeassistant.helpers.storage": storage,
        "homeassistant.exceptions": exceptions,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)

    package = types.ModuleType("ir_studio")
    package.__path__ = [str(ROOT)]
    monkeypatch.setitem(sys.modules, "ir_studio", package)

    websocket_stub = types.ModuleType("ir_studio.websocket")
    websocket_stub.register_commands = lambda _hass: None
    monkeypatch.setitem(sys.modules, "ir_studio.websocket", websocket_stub)

    closed = []

    class FailingHub:
        def __init__(self, *_args):
            pass

        async def connect(self):
            raise ConnectionError("simulated offline hub")

        async def close(self):
            closed.append(True)

    native_stub = types.ModuleType("ir_studio.native_transport")
    native_stub.NativeIRHub = FailingHub
    native_stub.validate_code = lambda value: value
    monkeypatch.setitem(sys.modules, "ir_studio.native_transport", native_stub)

    spec = importlib.util.spec_from_file_location(
        "ir_studio", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)]
    )
    integration = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "ir_studio", integration)
    spec.loader.exec_module(integration)

    class HTTP:
        async def async_register_static_paths(self, paths):
            registered_paths.extend(paths)

    class ConfigEntries:
        def async_entries(self, _domain):
            return [entry]

        async def async_forward_entry_setups(self, *_args):
            raise AssertionError("platform setup must not run after connect fails")

    class Entry:
        entry_id = "native-entry"
        options = {}
        data = {
            "kind": "native_hub",
            "device_id": "device-id",
            "host": "192.0.2.10",
            "local_key": "test-key",
            "protocol_version": "3.5",
        }

        def __init__(self):
            self.callbacks = []

        def async_on_unload(self, callback):
            self.callbacks.append(callback)

        def add_update_listener(self, callback):
            self.update_listener = callback
            return lambda: None

    async def executor_job(func, *args):
        return func(*args)

    hass = types.SimpleNamespace(
        data={},
        http=HTTP(),
        config_entries=ConfigEntries(),
        async_add_executor_job=executor_job,
    )
    entry = Entry()

    with pytest.raises(ConfigEntryNotReady):
        await integration.async_setup_entry(hass, entry)

    assert len(entry.callbacks) == 3
    assert registered_paths
    assert registered_panels
    assert hass.data["ir_studio"].panel_registered is True

    # Existing installations keep the advanced sidebar, but switching it off
    # via Configure must remove it without touching the physical transmitter.
    entry.options = {"show_panel": False}
    await integration._async_panel_options_changed(hass, entry)
    assert hass.data["ir_studio"].panel_registered is False
    assert removed_panels == ["ir-studio"]
    entry.options = {"show_panel": True}
    await integration._async_panel_options_changed(hass, entry)
    assert hass.data["ir_studio"].panel_registered is True
    assert registered_panels == ["ir-studio", "ir-studio"]

    for callback in reversed(entry.callbacks):
        result = callback()
        if inspect.isawaitable(result):
            await result

    assert closed == [True]
    assert removed_panels == ["ir-studio", "ir-studio"]
    assert "ir_studio" not in hass.data
    # Static paths and WebSocket registrations are process-wide and remain
    # marked so a later retry does not attempt to register them twice.
    assert hass.data["ir_studio_static_paths_registered"] is True
    assert hass.data["ir_studio_commands_registered"] is True
