"""Isolated service simulation, NOT a physical YRC11 test."""
from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
import types
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1] / 'custom_components' / 'ir_studio'


def install_stubs(monkeypatch):
    # The test runner has no Home Assistant installation. Minimal harmless
    # stubs exercise the job controller without a real host or Tuya access.
    names = [
        'ir_studio', 'homeassistant', 'homeassistant.components',
        'homeassistant.components.websocket_api', 'homeassistant.core',
        'homeassistant.helpers', 'homeassistant.helpers.entity_registry',
        'voluptuous'
    ]
    for name in names:
        m = types.ModuleType(name)
        if '.' not in name or name in ('ir_studio','homeassistant.components','homeassistant.helpers'):
            m.__path__ = []
        monkeypatch.setitem(sys.modules,name,m)
    sys.modules['ir_studio'].__path__=[str(ROOT)]
    vol=sys.modules['voluptuous']
    for name in ('Required','Optional','In','Coerce','Range','All'):
        setattr(vol,name,lambda *a,**k: (a[0] if a else None))
    ws=sys.modules['homeassistant.components.websocket_api']
    for name in ('websocket_command','require_admin','async_response'):
        if name=='websocket_command': setattr(ws,name,lambda schema:lambda fn:fn)
        else:setattr(ws,name,lambda fn:fn)
    core=sys.modules['homeassistant.core']
    core.Context=lambda user_id=None:types.SimpleNamespace(user_id=user_id)
    reg=sys.modules['homeassistant.helpers.entity_registry']
    reg.async_get=lambda hass:types.SimpleNamespace(async_get=lambda eid: types.SimpleNamespace(platform='tuya_ir',config_entry_id='entry-1'))


def load_ws(monkeypatch):
    install_stubs(monkeypatch)
    spec=importlib.util.spec_from_file_location('ir_studio.websocket',ROOT/'websocket.py')
    module=importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules,'ir_studio.websocket',module)
    spec.loader.exec_module(module)
    return module

class FakeCodeStore:
    def __init__(self):self.codes={}
    def get(self,device,command):return self.codes.get((device,command))

class Services:
    def __init__(self,store, *, fail=False):self.store=store;self.calls=[];self.fail=fail
    async def async_call(self, domain, service, data, blocking, context):
        self.calls.append((domain,service,data))
        if service=='learn_command':
            if self.fail:raise RuntimeError('HTTP 400 – No IR received from DP202')
            self.store.codes[(data['device'],data['command'][0])]='fake-base64-code' # simulation only

class FakeRuntime:
    def __init__(self,store):
        self.store=store;self.job_tasks={};self.profiles=[{'id':'p','name':'TCL','remote_entity':'remote.tuya_ir_hub','buttons':[{'id':'b','name':'Volume+','status':'pending','verified':False}]}]
        self.jobs={'j':{'id':'j','profile_id':'p','button_id':'b','kind':'learn','timeout':30,'status':'running'}}
        self.saves=0
    def find_profile(self,id):return self.profiles[0]
    def find_button(self,profile,id):return profile['buttons'][0]
    async def save(self):self.saves+=1

@pytest.mark.asyncio
async def test_external_remote_learning_is_unverified_without_foreign_store_access(monkeypatch):
    ws=load_ws(monkeypatch)
    store=FakeCodeStore();runtime=FakeRuntime(store)
    hass=types.SimpleNamespace(data={'tuya_ir':{'entry-1':types.SimpleNamespace(store=store)}},
             states={'remote.tuya_ir_hub':types.SimpleNamespace(state='on')},services=Services(store))
    await ws._run_service(hass,runtime,'j',user_id='admin')
    assert runtime.jobs['j']['status']=='done'
    assert runtime.profiles[0]['buttons'][0]['status']=='needs_check'
    assert runtime.profiles[0]['buttons'][0]['verified'] is False
    assert hass.services.calls[0][1]=='learn_command'

@pytest.mark.asyncio
async def test_failed_http400_does_not_claim_learned(monkeypatch):
    ws=load_ws(monkeypatch)
    store=FakeCodeStore();runtime=FakeRuntime(store)
    hass=types.SimpleNamespace(data={'tuya_ir':{'entry-1':types.SimpleNamespace(store=store)}},
         states={'remote.tuya_ir_hub':types.SimpleNamespace(state='on')},services=Services(store,fail=True))
    await ws._run_service(hass,runtime,'j',user_id='admin')
    assert runtime.jobs['j']['status']=='failed'
    assert runtime.profiles[0]['buttons'][0]['status']=='pending'
    assert store.get('TCL','Volume+') is None



class Connection:
    def __init__(self):
        self.results = []
        self.errors = []
        self.user = types.SimpleNamespace(id="admin")

    def send_result(self, id, value):
        self.results.append((id, value))

    def send_error(self, id, code, message):
        self.errors.append((id, code, message))


@pytest.mark.asyncio
async def test_job_cancel_marks_cancelling_until_worker_cleanup_completes(monkeypatch):
    ws = load_ws(monkeypatch)
    runtime = FakeRuntime(FakeCodeStore())
    done = asyncio.Event()

    async def worker():
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            await asyncio.sleep(0)
            runtime.jobs["j"]["status"] = "cancelled"
            done.set()
            raise

    task = asyncio.create_task(worker())
    await asyncio.sleep(0)
    runtime.job_tasks["j"] = task
    hass = types.SimpleNamespace(data={"ir_studio": runtime})
    conn = Connection()
    await ws.ws_job_cancel(hass, conn, {"id": 1, "job_id": "j"})
    assert conn.errors == []
    assert conn.results == [(1, {"status": "cancelling"})]
    assert runtime.jobs["j"]["status"] == "cancelling"
    await asyncio.gather(task, return_exceptions=True)
    await done.wait()
    assert runtime.jobs["j"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_does_not_cancel_send_jobs(monkeypatch):
    ws = load_ws(monkeypatch)
    runtime = FakeRuntime(FakeCodeStore())
    runtime.jobs["j"]["kind"] = "send"
    hass = types.SimpleNamespace(data={"ir_studio": runtime})
    conn = Connection()
    await ws.ws_job_cancel(hass, conn, {"id": 1, "job_id": "j"})
    assert len(conn.errors) == 1
    assert conn.errors[0][1] == "invalid_request"
    assert runtime.jobs["j"]["status"] == "running"




@pytest.mark.asyncio
async def test_explicit_user_template_only_adds_missing_buttons_and_never_drops_codes(monkeypatch):
    ws = load_ws(monkeypatch)
    runtime = FakeRuntime(FakeCodeStore())
    runtime.lock = asyncio.Lock()
    import json
    runtime.template_catalog = json.loads((ROOT / "presets.json").read_text())
    runtime.icons = json.loads((ROOT / "icon_catalog.json").read_text())["icons"]
    learned = {
        "id": "preserved", "name": "Power", "remote_name": "Power",
        "status": "stored", "verified": True,
    }
    runtime.profiles[0] = {
        "id": "p", "name": "Projector", "remote_device": "Projector",
        "remote_entity": "remote.test", "account_ref": "safe-account-ref",
        "buttons": [learned],
    }
    hass = types.SimpleNamespace(data={"ir_studio": runtime})
    connection = Connection()
    msg = {"id": 1, "profile_id": "p", "template_id": "tv_smart", "language": "ru"}
    await ws.ws_profile_apply_template(hass, connection, msg)
    assert not connection.errors
    assert connection.results[-1][1]["added"] == 14
    assert connection.results[-1][1]["total"] == 15
    profile = runtime.profiles[0]
    assert profile["buttons"][0] is learned
    assert profile["buttons"][0]["verified"] is True
    assert profile["buttons"][0]["status"] == "stored"
    assert profile["remote_device"] == "Projector"
    assert profile["remote_entity"] == "remote.test"
    assert profile["template_id"] == "tv_smart"
    assert any(b["remote_name"] == "Settings" for b in profile["buttons"])
    assert runtime.saves == 1

    await ws.ws_profile_apply_template(hass, connection, {**msg, "id": 2})
    assert connection.results[-1][1]["added"] == 0
    assert len(profile["buttons"]) == 15
    assert runtime.saves == 2


@pytest.mark.asyncio
async def test_manual_profile_type_never_invents_template_buttons(monkeypatch):
    ws = load_ws(monkeypatch)
    runtime = FakeRuntime(FakeCodeStore())
    runtime.lock = asyncio.Lock()
    import json
    runtime.template_catalog = json.loads((ROOT / "presets.json").read_text())
    runtime.icons = json.loads((ROOT / "icon_catalog.json").read_text())["icons"]
    hass = types.SimpleNamespace(
        data={"ir_studio": runtime},
        states={"remote.test": types.SimpleNamespace(state="on")},
    )
    conn = Connection()
    await ws.ws_profile_add(hass, conn, {
        "id": 1, "name": "Проектор", "entity_id": "remote.test",
        "profile_type": "projector", "language": "ru",
        "use_preset": False,
    })
    assert not conn.errors
    p = runtime.profiles[-1]
    assert p["profile_type"] == "projector"
    assert p["buttons"] == []
    assert p["template_id"] == ""
    assert p["button_origin"] == "manual"

    # Make the fake behave like StudioRuntime for multiple profile lookups.
    runtime.find_profile = lambda pid: next(
        profile for profile in runtime.profiles if profile["id"] == pid
    )
    # Changing type is only visual metadata, never creates IR commands.
    await ws.ws_profile_set_type(hass, conn, {
        "id": 2, "profile_id": p["id"], "profile_type": "tv_standard",
    })
    assert not conn.errors
    assert conn.results[-1][1]["buttons_added"] == 0
    assert p["profile_type"] == "tv_standard"
    assert p["buttons"] == []



@pytest.mark.asyncio
async def test_account_placeholder_cleanup_requires_explicit_choice_and_no_code(monkeypatch):
    ws = load_ws(monkeypatch)
    runtime = FakeRuntime(FakeCodeStore())
    runtime.lock = asyncio.Lock()
    runtime.ir_codes = {}
    runtime.native_codes = {}
    runtime.jobs = {}
    runtime.profiles[0].update({
        "account_ref": "legacy-account-ref",
        "remote_device": "Projector",
        "buttons": [
            {"id": "placeholder", "name": "Power",
             "remote_name": "Power", "status": "pending", "verified": False},
            {"id": "stored", "name": "Menu",
             "remote_name": "Menu", "status": "stored", "verified": False},
        ],
    })
    monkeypatch.setattr(ws, "_known_code", lambda *_: False)
    hass = types.SimpleNamespace(data={"ir_studio": runtime})
    connection = Connection()
    await ws.ws_profile_remove_unlearned(hass, connection, {
        "id": 1, "profile_id": "p", "button_ids": ["placeholder"],
    })
    assert not connection.errors
    assert connection.results[-1][1] == {
        "removed": 1, "remaining": 1, "codes_removed": 0,
    }
    assert [b["id"] for b in runtime.profiles[0]["buttons"]] == ["stored"]
    assert runtime.saves == 1


@pytest.mark.asyncio
async def test_account_cleanup_refuses_stored_or_unknown_ir_code(monkeypatch):
    ws = load_ws(monkeypatch)
    runtime = FakeRuntime(FakeCodeStore())
    runtime.lock = asyncio.Lock()
    runtime.ir_codes = {}
    runtime.native_codes = {}
    runtime.jobs = {}
    runtime.profiles[0].update({
        "account_ref": "legacy-ref",
        "buttons": [{"id": "b", "name": "Power",
                     "status": "pending", "verified": False}],
    })
    hass = types.SimpleNamespace(data={"ir_studio": runtime})
    connection = Connection()
    # An external remote driver with no introspection is NOT safe to prune.
    monkeypatch.setattr(ws, "_known_code", lambda *_: None)
    await ws.ws_profile_remove_unlearned(hass, connection, {
        "id": 1, "profile_id": "p", "button_ids": ["b"],
    })
    assert connection.errors[-1][1] == "invalid_request"
    assert len(runtime.profiles[0]["buttons"]) == 1

    # Even if the underlying driver reports no code, a signal in IR Studio's
    # own store must block deletion.
    monkeypatch.setattr(ws, "_known_code", lambda *_: False)
    runtime.native_codes["p/b"] = "PRIVATE_SIGNAL"
    await ws.ws_profile_remove_unlearned(hass, connection, {
        "id": 2, "profile_id": "p", "button_ids": ["b"],
    })
    assert connection.errors[-1][1] == "invalid_request"
    assert runtime.native_codes["p/b"] == "PRIVATE_SIGNAL"
    assert runtime.saves == 0



FLIPPER_RAW_FILE = """Filetype: IR signals file
Version: 1
#
name: Volume+
type: raw
frequency: 38000
duty_cycle: 0.330000
data: 9000 4500 563 563 563 1688 563 30000
#
name: PowerOn
type: raw
frequency: 38000
duty_cycle: 0.330000
data: 9000 4500 563 1688 563 563 563 30000
"""

@pytest.mark.asyncio
async def test_ir_file_preview_returns_names_not_waveforms(monkeypatch):
    ws = load_ws(monkeypatch)
    rt = FakeRuntime(FakeCodeStore())
    rt.native_remotes = {"remote.tuya_ir_hub": object()}
    hass = types.SimpleNamespace(data={"ir_studio": rt})
    conn = Connection()
    await ws.ws_ir_file_preview(hass, conn, {
        "id": 1, "profile_id": "p", "content": FLIPPER_RAW_FILE,
    })
    assert not conn.errors
    value = conn.results[-1][1]
    assert value["total"] == 2
    assert value["supported_names"] == ["Volume+", "PowerOn"]
    assert "code" not in repr(value)
    assert "9000" not in repr(value)


@pytest.mark.asyncio
async def test_ir_file_import_fills_existing_labels_and_preserves_originals(monkeypatch):
    import base64
    import struct

    ws = load_ws(monkeypatch)
    rt = FakeRuntime(FakeCodeStore())
    rt.lock = asyncio.Lock()
    rt.native_codes = {}
    rt.native_remotes = {"remote.tuya_ir_hub": types.SimpleNamespace(
        has_code=lambda device, command: command == "PowerOn")}
    rt.profiles[0]["buttons"].append({
        "id": "power", "name": "PowerOn", "remote_name": "PowerOn",
        "status": "verified", "verified": True,
    })
    rt.native_codes["p/power"] = "ORIGINAL_CODE"
    hass = types.SimpleNamespace(data={"ir_studio": rt})
    conn = Connection()
    msg = {"id": 2, "profile_id": "p", "content": FLIPPER_RAW_FILE,
           "mappings": [{"source_name": "Volume+", "button_id": "b"},
                        {"source_name": "PowerOn", "button_id": "power"}]}
    await ws.ws_ir_file_import(hass, conn, msg)
    assert conn.errors == []
    result = conn.results[-1][1]
    assert result["codes_imported"] == 1
    assert result["existing_preserved"] == 1
    assert result["needs_physical_test"] is True
    pulses = struct.unpack("<8H", base64.b64decode(rt.native_codes["p/b"]))
    assert pulses == (9000, 4500, 563, 563, 563, 1688, 563, 30000)
    assert rt.native_codes["p/power"] == "ORIGINAL_CODE"
    assert rt.profiles[0]["buttons"][0]["status"] == "stored"
    assert rt.profiles[0]["buttons"][0]["verified"] is False
    assert rt.saves == 1
    await ws.ws_ir_file_import(hass, conn, {**msg, "id": 3})
    assert conn.results[-1][1]["codes_imported"] == 0
    assert conn.results[-1][1]["existing_preserved"] == 2
    assert rt.saves == 1


@pytest.mark.asyncio
async def test_ir_file_import_rejects_wrong_profile_or_duplicate_targets(monkeypatch):
    ws = load_ws(monkeypatch)
    rt = FakeRuntime(FakeCodeStore())
    rt.lock = asyncio.Lock()
    rt.native_codes = {}
    rt.native_remotes = {"remote.tuya_ir_hub": types.SimpleNamespace(
        has_code=lambda device, command: False)}
    hass = types.SimpleNamespace(data={"ir_studio": rt})
    conn = Connection()
    msg = {"id": 1, "profile_id": "p", "content": FLIPPER_RAW_FILE,
           "mappings": [{"source_name": "Volume+", "button_id": "b"},
                        {"source_name": "PowerOn", "button_id": "b"}]}
    await ws.ws_ir_file_import(hass, conn, msg)
    assert conn.errors[-1][1] == "invalid_request"
    assert rt.native_codes == {}
    assert rt.saves == 0
    rt.native_remotes.clear()
    await ws.ws_ir_file_import(hass, conn, {
        **msg, "id": 2, "mappings": [{"source_name": "Volume+", "button_id": "b"}]
    })
    assert conn.errors[-1][1] == "invalid_request"
    assert rt.saves == 0


@pytest.mark.asyncio
async def test_ir_file_import_failed_persistence_restores_code_store(monkeypatch):
    ws = load_ws(monkeypatch)
    rt = FakeRuntime(FakeCodeStore())
    rt.lock = asyncio.Lock()
    rt.native_codes = {}
    rt.native_remotes = {"remote.tuya_ir_hub": types.SimpleNamespace(
        has_code=lambda device, command: False)}
    async def fail():
        raise RuntimeError("storage failure")
    rt.save = fail
    hass = types.SimpleNamespace(data={"ir_studio": rt})
    conn = Connection()
    await ws.ws_ir_file_import(hass, conn, {
        "id": 1, "profile_id": "p", "content": FLIPPER_RAW_FILE,
        "mappings": [{"source_name": "Volume+", "button_id": "b"}],
    })
    assert conn.errors[-1][1] == "import_failed"
    assert rt.native_codes == {}
    assert rt.profiles[0]["buttons"][0]["status"] == "pending"


