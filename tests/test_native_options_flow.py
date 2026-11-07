"""Native Configure wizard contract: clean HA device setup and learning.

Uses Home Assistant flow stubs, an actual async task and the same profile data
shape consumed by the real remote/button platforms. No network or IR emission.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import types

import voluptuous as vol

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "ir_studio"


@pytest.fixture
def env(monkeypatch):
    ha = types.ModuleType("homeassistant")
    ha.__path__ = []
    ce = types.ModuleType("homeassistant.config_entries")
    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    er = types.ModuleType("homeassistant.helpers.entity_registry")
    selectors = types.ModuleType("homeassistant.helpers.selector")

    class SelectSelectorConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class SelectSelector:
        def __init__(self, config):
            self.config = config

        def __call__(self, value):
            choices = [opt["value"] for opt in self.config.options]
            if value not in choices and not getattr(self.config, "custom_value", False):
                raise vol.Invalid("Unknown selection")
            return value

    class IconSelector:
        def __call__(self, value):
            if not isinstance(value, str) or not value.startswith("mdi:"):
                raise vol.Invalid("Not an MDI icon")
            return value

    selectors.IconSelector = IconSelector
    selectors.SelectSelector = SelectSelector
    selectors.SelectSelectorConfig = SelectSelectorConfig
    selectors.SelectSelectorMode = types.SimpleNamespace(DROPDOWN="dropdown")

    class OptionsFlow:
        def async_show_menu(self, **kwargs):
            return {"type": "menu", **kwargs}

        def async_show_form(self, **kwargs):
            return {"type": "form", **kwargs}

        def async_show_progress(self, **kwargs):
            return {"type": "progress", **kwargs}

        def async_show_progress_done(self, **kwargs):
            return {"type": "progress_done", **kwargs}

        def async_abort(self, **kwargs):
            return {"type": "abort", **kwargs}

        def async_create_entry(self, **kwargs):
            return {"type": "create_entry", **kwargs}

    ce.OptionsFlow = OptionsFlow
    ha.config_entries = ce
    er.async_get = lambda _hass: types.SimpleNamespace(
        async_get=lambda _id: types.SimpleNamespace(platform="ir_studio")
    )
    for m in (ha, ce, helpers, er, selectors):
        monkeypatch.setitem(sys.modules, m.__name__, m)
    package = types.ModuleType("ir_studio")
    package.__path__ = [str(ROOT)]
    monkeypatch.setitem(sys.modules, "ir_studio", package)
    spec = importlib.util.spec_from_file_location(
        "ir_studio.options_flow", ROOT / "options_flow.py"
    )
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)

    states = {
        "remote.hub": types.SimpleNamespace(
            entity_id="remote.hub", state="off",
            attributes={"friendly_name": "Bedroom IR", "supported_features": 3}
        ),
        "remote.virtual": types.SimpleNamespace(
            entity_id="remote.virtual", state="on",
            attributes={"ir_studio_virtual": True}
        ),
        "remote.dead": types.SimpleNamespace(
            entity_id="remote.dead", state="unavailable", attributes={}
        ),
    }

    class StateMachine:
        def async_all(self, domain):
            assert domain == "remote"
            return list(states.values())

        def get(self, name):
            return states.get(name)

    class Native:
        _entry = types.SimpleNamespace(entry_id="hub1")
        learned = set()

        def has_code(self, device, code):
            return (device, code) in self.learned

    native = Native()
    websocket = types.ModuleType("ir_studio.websocket")
    websocket._known_code = lambda _hass, profile, button: native.has_code(
        profile.get("remote_device", profile["name"]),
        button.get("remote_name", button["name"]),
    )
    monkeypatch.setitem(sys.modules, "ir_studio.websocket", websocket)
    calls = []

    async def service(domain, name, data, *, blocking=False):
        calls.append((domain, name, dict(data), blocking))
        if name == "learn_command":
            native.learned.add((data["device"], data["command"][0]))

    class Runtime:
        profiles = []
        icons = json.loads((ROOT / "icon_catalog.json").read_text())["icons"]
        template_catalog = json.loads((ROOT / "presets.json").read_text())
        native_remotes = {"remote.hub": native}
        ir_codes = {}
        native_codes = {}
        jobs = {}

        def __init__(self):
            import asyncio
            self.lock = asyncio.Lock()
            self.profiles = []
            self.ir_codes = {}
            self.native_codes = {}
            self.jobs = {}
            self.saved = 0

        async def save(self):
            self.saved += 1

        def find_profile(self, pid):
            return next(p for p in self.profiles if p["id"] == pid)

        def find_button(self, profile, bid):
            return next(b for b in profile["buttons"] if b["id"] == bid)

    runtime = Runtime()
    import asyncio
    hass = types.SimpleNamespace(
        data={"ir_studio": runtime},
        states=StateMachine(),
        services=types.SimpleNamespace(async_call=service),
        async_create_task=lambda coro: asyncio.create_task(coro),
    )
    flow = module.IRStudioOptionsFlow()
    flow.hass = hass
    flow.config_entry = types.SimpleNamespace(
        entry_id="hub1", options={"show_panel": False}
    )
    return types.SimpleNamespace(
        module=module, flow=flow, runtime=runtime, states=states,
        native=native, calls=calls,
    )


@pytest.mark.asyncio
async def test_create_remote_uses_existing_hub_without_blank_buttons(env):
    f = env.flow
    assert (await f.async_step_init())["menu_options"] == [
        "create_remote", "interface"
    ]
    result = await f.async_step_create_remote()
    assert result["step_id"] == "create_remote"
    schema = result["data_schema"].schema
    assert [key.schema for key in schema] == ["name", "icon"]  # single hub auto selected
    result = await f.async_step_create_remote({"name": "Desk lamp"})
    assert result["type"] == "menu"
    p = env.runtime.profiles[0]
    assert p["remote_entity"] == "remote.hub"
    assert p["remote_device"] == "Desk lamp"
    assert p["buttons"] == []  # no library placeholders
    assert p["icon"] == "blank_remote"
    assert env.runtime.saved == 1
    assert f._profile_id == p["id"]
    assert (await f.async_step_create_remote({"name": "Desk lamp"}))["errors"] == {
        "name": "name_exists"
    }


@pytest.mark.asyncio
async def test_learn_creates_persistent_entity_eligible_command_and_no_fake_codes(env):
    f = env.flow
    await f.async_step_create_remote({"name": "Desk lamp"})
    result = await f.async_step_add_command({"name": "Power"})
    assert result["type"] == "progress"
    assert result["step_id"] == "learn"
    assert env.runtime.profiles[0]["buttons"] == []
    await f._learn_task
    assert (await f.async_step_learn())["type"] == "progress_done"
    assert (await f.async_step_learn_done())["type"] == "menu"
    p = env.runtime.profiles[0]
    assert len(p["buttons"]) == 1
    b = p["buttons"][0]
    assert b["name"] == b["remote_name"] == "Power"
    assert b["status"] == "stored"
    assert b["verified"] is False
    assert env.runtime.saved == 2
    assert env.runtime.ir_codes == env.runtime.native_codes == {}
    assert env.calls == [("remote", "learn_command", {
        "entity_id": "remote.hub", "device": "Desk lamp",
        "command": ["Power"], "command_type": "ir", "timeout": 60
    }, True)]
    duplicate = await f.async_step_add_command({"name": "power"})
    assert duplicate["errors"] == {"name": "name_exists"}


@pytest.mark.asyncio
async def test_unavailable_hub_and_failed_learning_never_create_button(env):
    f = env.flow
    await f.async_step_create_remote({"name": "Desk lamp"})
    env.states["remote.hub"].state = "unavailable"
    result = await f.async_step_add_command({"name": "Power"})
    assert result["type"] == "form"
    assert result["errors"] == {"base": "no_hub"}
    assert env.runtime.profiles[0]["buttons"] == []
    env.states["remote.hub"].state = "off"
    env.states.pop("remote.hub")
    assert (await f.async_step_create_remote())["type"] == "abort"


@pytest.mark.asyncio
async def test_delete_button_and_profile_is_opt_in_and_preserves_external_codes(env):
    f = env.flow
    await f.async_step_create_remote({"name": "Desk lamp"})
    p = env.runtime.profiles[0]
    p["buttons"].append({
        "id": "button1", "name": "Mute", "remote_name": "Mute",
        "status": "stored", "verified": False,
    })
    env.runtime.native_codes[f"{p['id']}/button1"] = "imported-payload"
    selected = await f.async_step_manage_button({"button_id": "button1"})
    assert selected["type"] == "menu"
    assert {"test_button", "relearn_button", "rename_command", "remove_command"} <= set(selected["menu_options"])
    result = await f.async_step_remove_command({"confirm": False})
    assert result["errors"] == {"base": "confirmation_required"}
    assert p["buttons"]
    await f.async_step_remove_command({"confirm": True})
    assert p["buttons"] == []
    assert env.runtime.native_codes == {}
    # The physical driver's own store is not mutated by metadata deletion.
    env.native.learned.add(("Desk lamp", "Mute"))
    result = await f.async_step_remove_remote({"confirm": False})
    assert result["errors"] == {"base": "confirmation_required"}
    assert env.runtime.profiles == [p]
    assert (await f.async_step_remove_remote({"confirm": True}))["type"] == "abort"
    assert env.runtime.profiles == []
    assert ("Desk lamp", "Mute") in env.native.learned


@pytest.mark.asyncio
async def test_rename_does_not_modify_learned_namespaces(env):
    f = env.flow
    await f.async_step_create_remote({"name": "Desk lamp"})
    pid = f._profile_id
    result = await f.async_step_rename_remote({"name": "Bedroom lamp"})
    assert result["type"] == "menu"
    p = env.runtime.profiles[0]
    assert p["id"] == pid
    assert p["name"] == "Bedroom lamp"
    assert p["remote_device"] == "Desk lamp"


@pytest.mark.asyncio
async def test_panel_is_optional_and_off_in_new_config_entry(env):
    f = env.flow
    ui = await f.async_step_interface()
    assert ui["data_schema"]({"show_panel": False}) == {"show_panel": False}
    updated = await f.async_step_interface({"show_panel": True})
    assert updated["data"] == {"show_panel": True}


def test_new_native_integrations_hide_sidebar_by_default():
    src = (ROOT / "config_flow.py").read_text(encoding="utf-8")
    assert 'options={"show_panel": False}' in src
    init_src = (ROOT / "__init__.py").read_text(encoding="utf-8")
    assert 'entry.options.get("show_panel", True)' in init_src


@pytest.mark.asyncio
async def test_english_suggestions_and_custom_command_names(env):
    f = env.flow
    await f.async_step_create_remote({"name": "TCL"})
    result = await f.async_step_add_command()
    selector = next(v for k, v in result["data_schema"].schema.items()
                    if k.schema == "name")
    values = {item["value"] for item in selector.config.options}
    assert len(values) == 164
    assert {"POWER", "POWER ON", "POWER OFF", "VOL +", "MUTE", "MODE", "RGB", "FLASH"} <= values
    assert selector.config.custom_value is True
    assert selector("My original button") == "My original button"
    assert selector("Power") == "Power"


@pytest.mark.asyncio
async def test_rename_command_preserves_learned_code_key_and_identity(env):
    f = env.flow
    await f.async_step_create_remote({"name": "TCL"})
    profile = env.runtime.profiles[0]
    button = {"id": "stable-id", "name": "Power", "remote_name": "Power",
              "status": "stored", "verified": True}
    profile["buttons"].append(button)
    original = dict(button)

    choices = (await f.async_step_manage_actions())["menu_options"]
    assert "manage_button" in choices
    assert "change_icon" in choices
    selected = await f.async_step_manage_button({"button_id": "stable-id"})
    assert "rename_command" in selected["menu_options"]
    form = await f.async_step_rename_command()
    assert form["type"] == "form"
    selector = next(value for marker, value in form["data_schema"].schema.items()
                    if marker.schema == "name")
    assert selector.config.custom_value is True
    assert selector("My TV power") == "My TV power"

    result = await f.async_step_rename_command({
        "name": "My TV power"
    })
    assert result["type"] == "menu"
    assert button["name"] == "My TV power"
    for key in ("id", "remote_name", "status", "verified"):
        assert button[key] == original[key]

    profile["buttons"].append({
        "id": "other", "name": "Mute", "remote_name": "Mute",
        "status": "stored", "verified": False,
    })
    rejected = await f.async_step_rename_command({
        "name": "mute"
    })
    assert rejected["errors"] == {"name": "name_exists"}
    assert button["name"] == "My TV power"


@pytest.mark.asyncio
async def test_select_icon_at_creation_and_change_without_affecting_codes(env):
    f = env.flow
    form = await f.async_step_create_remote()
    selector = next(value for key, value in form["data_schema"].schema.items()
                    if key.schema == "icon")
    assert selector("mdi:television") == "mdi:television"
    await f.async_step_create_remote({"name": "TCL", "icon": "mdi:television-classic"})
    profile = env.runtime.profiles[0]
    assert profile["icon"] == "tv_standard"
    assert profile["icon_mdi"] == "mdi:television-classic"
    profile["buttons"].append({
        "id": "keep-me", "name": "Power", "remote_name": "Power",
        "status": "stored", "verified": True,
    })
    original = [dict(b) for b in profile["buttons"]]
    before = profile["remote_device"], profile["remote_entity"], profile["id"]
    result = await f.async_step_change_icon({"icon": "mdi:projector"})
    assert result["type"] == "menu"
    assert profile["icon"] == "projector"
    assert profile["buttons"] == original
    assert (profile["remote_device"], profile["remote_entity"], profile["id"]) == before

    rejected = await f.async_step_change_icon({"icon": "not-in-catalog"})
    assert rejected["errors"] == {"icon": "invalid_input"}
    assert profile["icon"] == "projector"
    assert profile["icon_mdi"] == "mdi:projector"



@pytest.mark.asyncio
async def test_manage_button_menu_send_once_then_relearn_preserves_uuid(env):
    flow = env.flow
    await flow.async_step_create_remote({"name": "TCL"})
    profile = env.runtime.profiles[0]
    item = {
        "id": "stable-button-uuid", "name": "Power (TCL)",
        "remote_name": "Power", "status": "verified", "verified": True,
    }
    profile["buttons"].append(item)
    menu = await flow.async_step_manage_actions()
    assert "manage_button" in menu["menu_options"]
    assert "rename_command" not in menu["menu_options"]
    selected = await flow.async_step_manage_button({"button_id": item["id"]})
    assert selected["menu_options"] == [
        "test_button", "relearn_button", "rename_command",
        "remove_command", "choose_another_button",
    ]

    # Do not accidentally toggle Power on merely opening the test form.
    preview = await flow.async_step_test_button()
    assert preview["type"] == "form"
    assert env.calls == []
    no_send = await flow.async_step_test_button({"confirm": False})
    assert no_send["errors"] == {"base": "confirmation_required"}
    assert env.calls == []
    tested = await flow.async_step_test_button({"confirm": True})
    assert tested["type"] == "menu"
    assert env.calls == [("remote", "send_command", {
        "entity_id": "remote.hub", "device": "TCL", "command": ["Power"]
    }, True)]

    # Relearning never creates an additional button or changes its entity id.
    begin = await flow.async_step_relearn_button({"confirm": True})
    assert begin["type"] == "progress"
    await flow._learn_task
    assert (await flow.async_step_learn())["type"] == "progress_done"
    done = await flow.async_step_learn_done()
    assert done["type"] == "menu"
    assert done["step_id"] == "button_actions"
    assert len(profile["buttons"]) == 1
    assert item["id"] == "stable-button-uuid"
    assert item["name"] == "Power (TCL)"
    assert item["remote_name"] == "Power"
    assert item["status"] == "stored"
    assert item["verified"] is False
    assert env.calls[1][1] == "learn_command"


@pytest.mark.asyncio
async def test_manage_button_rename_does_not_change_underlying_test_send(env):
    flow = env.flow
    await flow.async_step_create_remote({"name": "TCL"})
    profile = env.runtime.profiles[0]
    item = {
        "id": "stable", "name": "Power", "remote_name": "Power",
        "status": "stored", "verified": False,
    }
    profile["buttons"].append(item)
    await flow.async_step_manage_button({"button_id": "stable"})
    renamed = await flow.async_step_rename_command({"name": "My power key"})
    assert renamed["step_id"] == "button_actions"
    assert item["name"] == "My power key"
    assert item["remote_name"] == "Power"
    await flow.async_step_test_button({"confirm": True})
    assert env.calls[-1][2]["command"] == ["Power"]


def test_native_icon_selector_shows_real_preview_and_keeps_validated_mdi_format(env):
    flow = env.flow
    from ir_studio.icon_mdi import validate_mdi_icon
    selector = flow._icon_options()
    assert selector.__class__.__name__ == "IconSelector"
    assert selector("mdi:television") == "mdi:television"
    assert validate_mdi_icon("mdi:projector") == "mdi:projector"
    for bad in ("", "projector", "http://x", "mdi:<script>", "mdi:bad name"):
        with pytest.raises(ValueError):
            validate_mdi_icon(bad)
