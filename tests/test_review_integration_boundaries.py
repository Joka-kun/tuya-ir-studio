"""Regression gates for HACS review: IR Studio must own its auth and codes.

Fake remote backends raise on *any* attempt to read another integration's
hass.data. No credentials, cloud calls, or physical IR hardware are used.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import types

import pytest

from test_backup_websocket import Conn, RT, RAW
from test_job_simulation import load_ws


BASE = Path(__file__).resolve().parents[1] / "custom_components" / "ir_studio"


class IsolatedData(dict):
    def get(self, key, default=None):
        if key in ("tuya_local", "tuya_ir"):
            raise AssertionError(f"foreign runtime {key} inspected")
        return super().get(key, default)

    def __getitem__(self, key):
        if key in ("tuya_local", "tuya_ir"):
            raise AssertionError(f"foreign runtime {key} inspected")
        return super().__getitem__(key)


@pytest.mark.asyncio
async def test_raw_import_is_owned_by_ir_studio_not_tuya_ir(monkeypatch):
    ws = load_ws(monkeypatch)
    rt = RT()
    data = IsolatedData({"ir_studio": rt})
    hass = types.SimpleNamespace(data=data)
    conn = Conn()
    await ws.ws_import_raw(hass, conn, {
        "id": 40, "profile_id": "existing", "button_id": "power",
        "payload": RAW, "format": "raw_ir",
    })
    assert conn.error is None
    assert conn.result["stored"] is True
    assert conn.result["sendable_via_bound_remote"] is False
    assert rt.ir_codes == {"existing/power": RAW}
    assert rt.native_codes == {}
    assert rt.profiles[0]["buttons"][0]["status"] == "needs_check"
    assert rt.profiles[0]["buttons"][0]["verified"] is False
    assert rt.saves == 1

    # Export must carry our waveform without querying the foreign store.
    await ws.ws_backup_export(hass, conn, {
        "id": 41, "profile_ids": ["existing"],
    })
    assert conn.error is None
    button = conn.result["profiles"][0]["buttons"][0]
    assert button["raw_ir"] == RAW
    assert conn.result["raw_ir_codes_included"] == 1

    await ws.ws_get(hass, conn, {"id": 42})
    own_button = conn.result["profiles"][0]["buttons"][0]
    assert own_button["code_in_local_store"] is True
    assert own_button["code_in_tuya_ir_store"] is None


@pytest.mark.asyncio
async def test_foreign_codes_remain_unknown_even_if_other_backend_has_data(monkeypatch):
    ws = load_ws(monkeypatch)
    rt = RT()
    hass = types.SimpleNamespace(data=IsolatedData({"ir_studio": rt}))
    conn = Conn()
    await ws.ws_get(hass, conn, {"id": 43})
    button = conn.result["profiles"][0]["buttons"][0]
    assert button["code_in_local_store"] is None
    assert button["code_in_tuya_ir_store"] is None
    assert ws._known_code(hass, rt.profiles[0], rt.profiles[0]["buttons"][0]) is None

    await ws.ws_backup_export(hass, conn, {
        "id": 44, "profile_ids": ["existing"],
    })
    assert conn.result["raw_ir_codes_included"] == 0
    assert conn.result["raw_ir_codes_unavailable"] == 1


@pytest.mark.asyncio
async def test_raw_import_rolls_back_if_own_storage_write_fails(monkeypatch):
    ws = load_ws(monkeypatch)
    rt = RT()
    before = dict(rt.profiles[0]["buttons"][0])
    async def fail_save():
        raise OSError("synthetic storage error")
    rt.save = fail_save
    hass = types.SimpleNamespace(data=IsolatedData({"ir_studio": rt}))
    conn = Conn()
    await ws.ws_import_raw(hass, conn, {
        "id": 45, "profile_id": "existing", "button_id": "power",
        "payload": RAW, "format": "raw_ir",
    })
    assert conn.error is not None
    assert rt.ir_codes == {}
    assert rt.profiles[0]["buttons"][0] == before


def test_no_private_foreign_runtime_access_in_our_code():
    for file in BASE.glob("*.py"):
        source = file.read_text(encoding="utf-8")
        for forbidden in (
            'hass.data.get("tuya_local"',
            "hass.data.get('tuya_local'",
            'hass.data["tuya_local"]',
            "hass.data['tuya_local']",
            'hass.data.get("tuya_ir"',
            "hass.data.get('tuya_ir'",
            'hass.data["tuya_ir"]',
            "hass.data['tuya_ir']",
        ):
            assert forbidden not in source, (file.name, forbidden)
