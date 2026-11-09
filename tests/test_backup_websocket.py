"""The admin backup WebSocket handlers in isolation (not a physical device test)."""
from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
import struct
import types

import pytest

from test_job_simulation import load_ws

RAW = base64.b64encode(struct.pack("<" + "H" * 32, *([9000, 4500] + [570, 580] * 15))).decode()


class Conn:
    def __init__(self):
        self.result = None
        self.error = None
    def send_result(self, ident, result):
        self.result = result
    def send_error(self, ident, code, msg):
        self.error = (code, msg)


class RT:
    def __init__(self):
        self.profiles = [{"id": "existing", "name": "TV", "remote_entity": "remote.hub",
                          "remote_device": "TV", "buttons": [{"id": "power", "name": "Power", "status": "stored", "verified": False}]}]
        self.ir_codes = {}
        self.native_codes = {}
        self.native_remotes = {}
        self.lock = asyncio.Lock()
        self.jobs = {}
        self.presets = {}
        catalog_path = Path(__file__).resolve().parents[1] / "custom_components" / "ir_studio" / "presets.json"
        self.template_catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        self.icons = json.loads((catalog_path.parent / "icon_catalog.json").read_text(encoding="utf-8"))["icons"]
        self.saves = 0
    def find_profile(self, profile_id):
        return next(p for p in self.profiles if p["id"] == profile_id)
    def find_button(self, profile, button_id):
        return next(b for b in profile["buttons"] if b["id"] == button_id)
    async def save(self):
        self.saves += 1


@pytest.mark.asyncio
async def test_admin_export_contains_raw_but_not_sensitive_runtime(monkeypatch):
    ws = load_ws(monkeypatch)
    rt = RT()
    rt.ir_codes["existing/power"] = RAW
    hass = types.SimpleNamespace(data={"ir_studio": rt})
    conn = Conn()
    await ws.ws_backup_export(hass, conn, {"id": 1, "profile_ids": ["existing"]})
    assert conn.error is None
    assert conn.result["raw_ir_codes_included"] == 1
    assert conn.result["profiles"][0]["buttons"][0]["raw_ir"] == RAW
    assert "local_key" not in repr(conn.result)
    assert "access_token" not in repr(conn.result)


@pytest.mark.asyncio
async def test_import_preview_does_not_mutate_and_commit_stores_raw(monkeypatch):
    ws = load_ws(monkeypatch)
    rt = RT()
    hass = types.SimpleNamespace(data={"ir_studio": rt})
    conn = Conn()
    new = {"id": "new", "name": "Projector", "remote_entity": "remote.hub",
           "buttons": [{"id": "b2", "name": "Power", "raw_ir": RAW, "status": "verified"}]}
    payload = {"format": "tuya-ir-studio-backup", "format_version": 2, "profiles": [new]}
    msg = {"id": 3, "backup": payload, "profile_ids": ["new"], "strategy": "skip", "dry_run": True}
    await ws.ws_backup_import(hass, conn, msg)
    assert conn.error is None
    assert conn.result["dry_run"]
    assert rt.saves == 0 and len(rt.profiles) == 1 and not rt.ir_codes
    await ws.ws_backup_import(hass, conn, {**msg, "dry_run": False})
    assert rt.saves == 1 and len(rt.profiles) == 2
    assert rt.ir_codes["new/b2"] == RAW
    assert rt.profiles[1]["buttons"][0]["status"] == "needs_check"
    assert "raw_ir" not in rt.profiles[1]["buttons"][0]


@pytest.mark.asyncio
async def test_invalid_import_keeps_profiles_and_codes(monkeypatch):
    ws = load_ws(monkeypatch)
    rt = RT()
    hass = types.SimpleNamespace(data={"ir_studio": rt})
    conn = Conn()
    old = repr(rt.profiles)
    await ws.ws_backup_import(hass, conn, {"id": 4, "backup": {"format": "unknown"},
                      "profile_ids": ["no"], "strategy": "replace", "dry_run": False})
    assert conn.error is not None
    assert repr(rt.profiles) == old
    assert not rt.ir_codes and rt.saves == 0

@pytest.mark.asyncio
async def test_native_dp202_selective_backup_import_and_export(monkeypatch):
    ws = load_ws(monkeypatch)
    rt = RT()
    rt.native_codes["existing/power"] = "1TUYACODE12345"
    hass = types.SimpleNamespace(data={"ir_studio": rt})
    conn = Conn()
    await ws.ws_backup_export(hass, conn, {"id": 8, "profile_ids": ["existing"]})
    assert conn.error is None
    exported = conn.result
    assert exported["format_version"] == 3
    assert exported["raw_ir_codes_included"] == 1
    assert exported["profiles"][0]["buttons"][0]["tuya_code"] == "1TUYACODE12345"
    # Imported profile receives the native code in a separate Store.
    new_backup = {**exported, "profiles": [
        {**exported["profiles"][0], "id": "another", "name": "Projector",
         "buttons": [{**exported["profiles"][0]["buttons"][0], "id": "power2"}]}
    ]}
    await ws.ws_backup_import(hass, conn, {
        "id": 9, "backup": new_backup, "profile_ids": ["another"],
        "strategy": "skip", "dry_run": False,
    })
    assert conn.error is None
    assert rt.native_codes["another/power2"] == "1TUYACODE12345"
    assert rt.native_codes["existing/power"] == "1TUYACODE12345"
    assert rt.profiles[-1]["buttons"][0]["status"] == "needs_check"
    assert "tuya_code" not in rt.profiles[-1]["buttons"][0]


@pytest.mark.asyncio
async def test_profile_and_button_deletion_remove_only_studio_owned_payloads(monkeypatch):
    ws = load_ws(monkeypatch)
    rt = RT()
    rt.ir_codes = {"existing/power": RAW, "other/button": RAW}
    rt.native_codes = {"existing/power": "DP202", "other/button": "OTHER"}
    hass = types.SimpleNamespace(data={"ir_studio": rt})
    conn = Conn()

    await ws.ws_button_delete(hass, conn, {
        "id": 20, "profile_id": "existing", "button_id": "power"
    })
    assert conn.error is None
    assert rt.ir_codes == {"other/button": RAW}
    assert rt.native_codes == {"other/button": "OTHER"}

    await ws.ws_profile_delete(hass, conn, {"id": 21, "profile_id": "existing"})
    assert conn.error is None
    assert rt.ir_codes == {"other/button": RAW}
    assert rt.native_codes == {"other/button": "OTHER"}


@pytest.mark.asyncio
async def test_replace_backup_removes_stale_studio_payloads_before_restore(monkeypatch):
    ws = load_ws(monkeypatch)
    rt = RT()
    rt.ir_codes = {"existing/power": RAW}
    rt.native_codes = {"existing/power": "OLD"}
    hass = types.SimpleNamespace(data={"ir_studio": rt})
    conn = Conn()
    backup = {
        "format": "tuya-ir-studio-backup",
        "format_version": 3,
        "profiles": [{
            "id": "existing",
            "name": "TV",
            "remote_entity": "remote.hub",
            "remote_device": "TV",
            "buttons": [{
                "id": "new-power",
                "name": "Power",
                "remote_name": "Power",
                "tuya_code": "NEW-DP202",
                "status": "stored",
            }],
        }],
    }
    await ws.ws_backup_import(hass, conn, {
        "id": 22,
        "backup": backup,
        "profile_ids": ["existing"],
        "strategy": "replace",
        "dry_run": False,
    })
    assert conn.error is None
    assert rt.ir_codes == {}
    assert rt.native_codes == {"existing/new-power": "NEW-DP202"}


@pytest.mark.asyncio
async def test_template_profile_and_button_set_handlers_are_imported_and_callable(monkeypatch):
    ws = load_ws(monkeypatch)
    rt = RT()
    states = types.SimpleNamespace(get=lambda _entity: types.SimpleNamespace(state="on"))
    hass = types.SimpleNamespace(data={"ir_studio": rt}, states=states)
    conn = Conn()

    await ws.ws_profile_add(hass, conn, {
        "id": 23,
        "name": "Living room TV",
        "entity_id": "remote.hub",
        "template_id": "tv_standard",
        "language": "en",
    })
    assert conn.error is None
    profile_id = conn.result["id"]
    profile = rt.find_profile(profile_id)
    assert profile["buttons"]
    assert all("template_id" not in button for button in profile["buttons"])

    await ws.ws_button_add_set(hass, conn, {
        "id": 24,
        "profile_id": profile_id,
        "set_ids": ["audio"],
        "command_ids": ["power"],
        "language": "en",
    })
    assert conn.error is None
    names = [button["remote_name"] for button in profile["buttons"]]
    assert len(names) == len(set(name.casefold() for name in names))


@pytest.mark.asyncio
async def test_native_dp202_import_uses_typed_payload_field(monkeypatch):
    ws = load_ws(monkeypatch)
    rt = RT()
    rt.native_remotes["remote.hub"] = object()
    hass = types.SimpleNamespace(data={"ir_studio": rt})
    ws.er.async_get = lambda _hass: types.SimpleNamespace(
        async_get=lambda _entity_id: types.SimpleNamespace(
            platform="ir_studio", config_entry_id="native-entry"
        )
    )
    conn = Conn()

    await ws.ws_import_raw(hass, conn, {
        "id": 25,
        "profile_id": "existing",
        "button_id": "power",
        "payload": "DP202-OPAQUE-PAYLOAD",
        "format": "tuya_dp202",
    })
    assert conn.error is None
    assert conn.result["format"] == "tuya_dp202"
    assert rt.native_codes["existing/power"] == "DP202-OPAQUE-PAYLOAD"
    assert rt.profiles[0]["buttons"][0]["status"] == "stored"



@pytest.mark.asyncio
async def test_icon_change_updates_only_visual_metadata(monkeypatch):
    ws = load_ws(monkeypatch)
    runtime = RT()
    runtime.native_codes["existing/power"] = "KNOWN-DP202"
    runtime.ir_codes["existing/power"] = "KNOWN-RAW"
    from copy import deepcopy
    button_before = deepcopy(runtime.profiles[0]["buttons"])
    hass = types.SimpleNamespace(data={"ir_studio": runtime})
    conn = Conn()

    await ws.ws_profile_set_icon(hass, conn, {
        "id": 70, "profile_id": "existing", "icon": "lamp",
    })
    assert conn.error is None
    assert conn.result == {"icon": "lamp", "buttons_added": 0}
    assert runtime.profiles[0]["icon"] == "lamp"
    assert runtime.profiles[0]["buttons"] == button_before
    assert runtime.profiles[0]["remote_device"] == "TV"
    assert runtime.profiles[0]["remote_entity"] == "remote.hub"
    assert runtime.native_codes["existing/power"] == "KNOWN-DP202"
    assert runtime.ir_codes["existing/power"] == "KNOWN-RAW"
    assert runtime.saves == 1

    invalid = Conn()
    await ws.ws_profile_set_icon(hass, invalid, {
        "id": 71, "profile_id": "existing", "icon": "evil_mdi:script",
    })
    assert invalid.error is not None
    assert runtime.profiles[0]["icon"] == "lamp"
    assert runtime.saves == 1



@pytest.mark.asyncio
async def test_profile_drag_order_persists_and_preserves_ir_signal_keys(monkeypatch):
    """Moving profiles must not mutate names, commands, UUIDs or code stores."""
    ws = load_ws(monkeypatch)
    rt = RT()
    rt.profiles.extend([
        {"id": "second", "name": "Projector", "remote_device": "Projector",
         "remote_entity": "remote.hub", "buttons": []},
        {"id": "third", "name": "Lamp", "remote_device": "Lamp",
         "remote_entity": "remote.hub", "buttons": []},
    ])
    rt.ir_codes["existing/power"] = RAW
    rt.native_codes["existing/power"] = "DP202-KEEP"
    snapshots = []
    original_save = rt.save

    async def capture_save():
        await original_save()
        snapshots.append([p["id"] for p in rt.profiles])

    rt.save = capture_save
    hass = types.SimpleNamespace(data={"ir_studio": rt})
    conn = Conn()
    before = json.dumps(rt.profiles, sort_keys=True)
    await ws.ws_profile_reorder(hass, conn, {
        "id": 60, "profile_id": "third",
        "target_profile_id": "existing", "position": "before",
    })
    assert conn.error is None and conn.result == {"moved": True}
    assert [p["id"] for p in rt.profiles] == ["third", "existing", "second"]
    assert snapshots == [["third", "existing", "second"]]
    assert rt.ir_codes == {"existing/power": RAW}
    assert rt.native_codes == {"existing/power": "DP202-KEEP"}
    assert json.loads(before)[0] == rt.profiles[1]
    assert rt.profiles[0]["remote_device"] == "Lamp"

    await ws.ws_profile_reorder(hass, conn, {
        "id": 61, "profile_id": "third",
        "target_profile_id": "existing", "position": "before",
    })
    assert conn.result == {"moved": False}
    assert rt.saves == 1

    await ws.ws_profile_reorder(hass, conn, {
        "id": 62, "profile_id": "third",
        "target_profile_id": "third", "position": "after",
    })
    assert conn.result == {"moved": False} and rt.saves == 1


@pytest.mark.asyncio
async def test_profile_reorder_rejects_stale_ids_and_restores_order_on_failed_save(monkeypatch):
    ws = load_ws(monkeypatch)
    rt = RT()
    rt.profiles.append({
        "id": "second", "name": "Second", "remote_entity": "remote.hub",
        "remote_device": "Second", "buttons": [],
    })
    rt.ir_codes["existing/power"] = RAW
    hass = types.SimpleNamespace(data={"ir_studio": rt})
    conn = Conn()
    original_list = rt.profiles
    initial = [p["id"] for p in original_list]

    await ws.ws_profile_reorder(hass, conn, {
        "id": 63, "profile_id": "absent",
        "target_profile_id": "second", "position": "after",
    })
    assert conn.error and conn.error[0] == "invalid_request"
    assert [p["id"] for p in rt.profiles] == initial
    assert rt.saves == 0

    async def fail_save():
        raise OSError("Simulated disk failure: no private payload should escape")

    rt.save = fail_save
    conn = Conn()
    await ws.ws_profile_reorder(hass, conn, {
        "id": 64, "profile_id": "second",
        "target_profile_id": "existing", "position": "before",
    })
    assert conn.error and conn.error[0] == "save_failed"
    assert "Simulated disk" not in conn.error[1]
    assert rt.profiles is original_list
    assert [p["id"] for p in rt.profiles] == initial
    assert rt.ir_codes["existing/power"] == RAW


@pytest.mark.asyncio
async def test_import_binding_picks_current_ha_remote_without_changing_ir_keys(monkeypatch):
    ws = load_ws(monkeypatch)
    rt = RT()
    rt.ir_codes["existing/power"] = RAW
    states = types.SimpleNamespace(get=lambda key: {
        "remote.lan_hub": types.SimpleNamespace(state="off", attributes={}),
        "remote.old_hub": None,
    }.get(key))
    hass = types.SimpleNamespace(data={"ir_studio": rt}, states=states)
    conn = Conn()
    backup = {"format": "tuya-ir-studio-backup", "format_version": 3,
              "profiles": [{
                  "id": "new", "name": "Bedroom TV",
                  "remote_entity": "remote.old_hub", "remote_device": "Bedroom TV",
                  "buttons": [{"id": "power", "name": "Power",
                               "remote_name": "Power", "status": "verified",
                               "raw_ir": RAW}]
              }]}
    args = {"id": 48, "backup": backup, "profile_ids": ["new"],
            "strategy": "skip", "remote_bindings": {"new": "remote.lan_hub"}}
    await ws.ws_backup_import(hass, conn, {**args, "dry_run": True})
    assert conn.error is None
    assert rt.saves == 0 and len(rt.profiles) == 1
    await ws.ws_backup_import(hass, conn, {**args, "dry_run": False})
    assert conn.error is None
    imported = rt.profiles[-1]
    assert imported["remote_entity"] == "remote.lan_hub"
    assert imported["remote_device"] == "Bedroom TV"
    assert imported["buttons"][0]["remote_name"] == "Power"
    assert imported["buttons"][0]["verified"] is False
    assert rt.ir_codes["new/power"] == RAW
    assert rt.ir_codes["existing/power"] == RAW


@pytest.mark.asyncio
async def test_existing_profile_binding_merge_replace_and_skip(monkeypatch):
    ws = load_ws(monkeypatch)
    rt = RT()
    rt.native_codes["existing/power"] = "1OLDNATIVECODE"
    hass = types.SimpleNamespace(
        data={"ir_studio": rt},
        states=types.SimpleNamespace(get=lambda key:
            types.SimpleNamespace(state="on", attributes={})
            if key == "remote.new_hub" else None))
    conn = Conn()
    backup = {"format": "tuya-ir-studio-backup", "format_version": 3,
              "profiles": [{
                  "id": "existing", "name": "TV", "remote_device": "TV",
                  "remote_entity": "remote.old_hub",
                  "buttons": [{"id": "power", "name": "Power",
                               "remote_name": "Power", "status": "stored"}]
              }]}
    args = {"id": 49, "backup": backup, "profile_ids": ["existing"],
            "remote_bindings": {"existing": "remote.new_hub"}, "dry_run": False}
    await ws.ws_backup_import(hass, conn, {**args, "strategy": "skip"})
    assert conn.error is None
    assert rt.profiles[0]["remote_entity"] == "remote.hub"
    await ws.ws_backup_import(hass, conn, {**args, "strategy": "merge"})
    assert conn.error is None
    assert rt.profiles[0]["remote_entity"] == "remote.new_hub"
    assert rt.profiles[0]["remote_device"] == "TV"
    assert rt.native_codes["existing/power"] == "1OLDNATIVECODE"
    assert conn.result["changes"]["rebound_profiles"] == ["TV"]
    await ws.ws_backup_import(hass, conn, {**args, "strategy": "replace"})
    assert conn.error is None
    assert rt.profiles[0]["remote_entity"] == "remote.new_hub"
    assert rt.profiles[0]["id"] == "existing"
    assert rt.profiles[0]["buttons"][0]["remote_name"] == "Power"


@pytest.mark.asyncio
@pytest.mark.parametrize("state,attrs", [
    ("unavailable", {}), ("unknown", {}), ("on", {"ir_studio_virtual": True}),
    (None, None),
])
async def test_backup_import_rejects_unavailable_or_virtual_transmitters(
        monkeypatch, state, attrs):
    ws = load_ws(monkeypatch)
    rt = RT()
    old = repr(rt.profiles)
    states = types.SimpleNamespace(get=lambda key:
        types.SimpleNamespace(state=state, attributes=attrs)
        if key == "remote.invalid" and state is not None else None)
    hass = types.SimpleNamespace(data={"ir_studio": rt}, states=states)
    conn = Conn()
    backup = {"format": "tuya-ir-studio-backup", "format_version": 3,
              "profiles": [{"id": "other", "name": "Other",
                            "remote_entity": "remote.old",
                            "buttons": [{"id": "b", "name": "Power"}]}]}
    await ws.ws_backup_import(hass, conn, {
        "id": 50, "backup": backup, "profile_ids": ["other"],
        "remote_bindings": {"other": "remote.invalid"},
        "strategy": "skip", "dry_run": False,
    })
    assert conn.error is not None
    assert repr(rt.profiles) == old and rt.saves == 0
    assert rt.ir_codes == {} and rt.native_codes == {}


@pytest.mark.asyncio
async def test_backup_import_rejects_binding_for_unselected_profile(monkeypatch):
    ws = load_ws(monkeypatch)
    rt = RT()
    hass = types.SimpleNamespace(data={"ir_studio": rt})
    conn = Conn()
    backup = {"format": "tuya-ir-studio-backup", "format_version": 3,
              "profiles": [{"id": "new", "name": "TV2", "remote_entity": "remote.old",
                            "buttons": [{"id": "b", "name": "Power"}]}]}
    await ws.ws_backup_import(hass, conn, {
        "id": 51, "backup": backup, "profile_ids": ["new"],
        "remote_bindings": {"different": "remote.hub"},
        "strategy": "skip", "dry_run": False,
    })
    assert conn.error is not None and rt.saves == 0
