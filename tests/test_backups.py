"""Portable backup tests. No Home Assistant installation required."""
from __future__ import annotations

import base64
import importlib.util
from pathlib import Path
import struct
import sys
import types

import pytest

MODULE_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "ir_studio"
sys.modules.setdefault("ir_studio", types.ModuleType("ir_studio"))
sys.modules["ir_studio"].__path__ = [str(MODULE_DIR)]
spec = importlib.util.spec_from_file_location("ir_studio.backup", MODULE_DIR / "backup.py")
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)

RAW = base64.b64encode(struct.pack("<" + "H" * 32, *([9000, 4500] + [570, 580] * 15))).decode()


def sample(name="TV", pid="p1", bid="b1", raw=True):
    button = {"id": bid, "name": "Power", "remote_name": "Power_original", "status": "verified", "verified": True}
    if raw:
        button["raw_ir"] = RAW
    return {"id": pid, "name": name, "remote_entity": "remote.hub", "remote_device": "TV_original", "buttons": [button]}


def document(*profiles):
    return {"format": backup.FORMAT, "format_version": 2, "profiles": list(profiles)}


def test_backup_normalize_preserves_remote_storage_keys_and_ids():
    result = backup.normalize_backup(document(sample()))
    assert result[0]["id"] == "p1"
    assert result[0]["remote_device"] == "TV_original"
    assert result[0]["buttons"][0]["remote_name"] == "Power_original"
    assert result[0]["buttons"][0]["raw_ir"] == RAW
    assert not result[0]["buttons"][0]["verified"]
    assert result[0]["buttons"][0]["status"] == "needs_check"


def test_export_only_allowlisted_fields_never_secrets():
    p = sample(raw=False)
    p["local_key"] = "SECRET"
    p["buttons"][0]["client_secret"] = "SECRET"
    data, count = backup.strip_export_profile(p, lambda profile, btn: RAW)
    assert count == 1
    assert "SECRET" not in repr(data)
    assert data["buttons"][0]["raw_ir"] == RAW


def test_select_only_one_profile():
    target, report = backup.make_import_plan([], document(sample(), sample("Lamp", "p2", "b2")), ["p2"], "skip")
    assert len(target) == 1
    assert target[0]["name"] == "Lamp"
    assert report["added_profiles"] == ["Lamp"]


def test_existing_untouched_for_skip():
    original = sample(raw=False)
    target, report = backup.make_import_plan([original], document(sample(raw=True)), ["p1"], "skip")
    assert target == [original]
    assert report["skipped_profiles"] == ["TV"]
    assert report["raw_codes"] == 0
    assert "raw_ir" not in target[0]["buttons"][0]


def test_merge_is_nondestructive_and_idempotent():
    old = sample(raw=False)
    inc = sample(raw=True)
    inc["buttons"].append({"id": "b2", "name": "Mute", "status": "stored", "raw_ir": RAW})
    first, report = backup.make_import_plan([old], document(inc), ["p1"], "merge")
    assert first[0]["buttons"][0] == old["buttons"][0]
    assert [b["name"] for b in first[0]["buttons"]] == ["Power", "Mute"]
    assert report["added_buttons"] == 1
    assert report["raw_codes"] == 1  # Only the newly added button's payload counts.
    second, again = backup.make_import_plan(first, document(inc), ["p1"], "merge")
    assert second == first
    assert again["added_buttons"] == 0


def test_replace_keeps_ha_profile_id_and_doesnt_modify_input():
    old = sample("TV", "old-id", "b1", raw=False)
    new = sample("TV", "new-id", "b2")
    target, changes = backup.make_import_plan([old], document(new), ["new-id"], "replace")
    assert target[0]["id"] == "old-id"
    assert [b["id"] for b in target[0]["buttons"]] == ["b2"]
    assert old["buttons"][0]["id"] == "b1"
    assert changes["replaced_profiles"] == ["TV"]
    assert changes["raw_codes"] == 1


def test_supports_legacy_v03_full_and_single_exports():
    p = sample(raw=False)
    result = backup.normalize_backup({"format": "ir-studio-backup", "format_version": 1, "profiles": [p]})
    assert result[0]["buttons"][0]["remote_name"] == "Power_original"
    one = backup.normalize_backup({"format": "ir-studio-profile", "format_version": 1, "profile": p})
    assert one[0]["name"] == "TV"


@pytest.mark.parametrize("payload", [
    {}, {"format": backup.FORMAT, "format_version": 999, "profiles": []},
    document({**sample(), "remote_entity": "light.fake"}),
    document({**sample(), "buttons": [sample()["buttons"][0]] * 2}),
    document({**sample(), "buttons": [{**sample()["buttons"][0], "raw_ir": "BAD"}]}),
    document(sample(), sample("TV", "p2", "b2")),
])
def test_invalid_backup_is_rejected_without_mutation(payload):
    original = [sample(raw=False)]
    from copy import deepcopy
    snapshot = deepcopy(original)
    with pytest.raises(ValueError):
        backup.make_import_plan(original, payload, ["p1"], "merge")
    assert original == snapshot


def test_unknown_selection_rejected():
    with pytest.raises(ValueError, match="absent"):
        backup.make_import_plan([], document(sample()), ["nonexistent"], "skip")



def test_native_opaque_dp202_backup_round_trip():
    original = sample(raw=False)
    original["buttons"][0]["tuya_code"] = "1abcDEF42"
    document_v3 = {"format": backup.FORMAT, "format_version": 3, "profiles": [original]}
    decoded = backup.normalize_backup(document_v3)
    assert decoded[0]["buttons"][0]["tuya_code"] == "1abcDEF42"
    exported, count = backup.strip_export_profile(
        decoded[0], lambda _p, _b: {"format": "tuya_dp202", "code": "1abcDEF42"}
    )
    assert count == 1
    assert exported["buttons"][0]["tuya_code"] == "1abcDEF42"
    imported, changes = backup.make_import_plan([], document_v3, ["p1"], "skip")
    assert imported[0]["buttons"][0]["tuya_code"] == "1abcDEF42"
    assert changes["raw_codes"] == 1


def test_reject_ambiguous_tuya_and_raw_payloads():
    profile = sample()
    profile["buttons"][0]["tuya_code"] = "A123"
    with pytest.raises(ValueError, match="Ambiguous"):
        backup.normalize_backup({"format": backup.FORMAT, "format_version": 3, "profiles": [profile]})



def test_icon_metadata_survives_portable_backup_and_replace():
    existing = sample(raw=False)
    existing["icon"] = "projector"
    existing["icon_mdi"] = "mdi:projector"
    packed, _ = backup.strip_export_profile(existing)
    assert packed["icon"] == "projector"
    assert packed["icon_mdi"] == "mdi:projector"
    restored = backup.normalize_backup(document(packed))
    assert restored[0]["icon"] == "projector"
    replacement, _ = backup.make_import_plan([sample(raw=False)], document(packed), ["p1"], "replace")
    assert replacement[0]["icon"] == "projector"
    assert replacement[0]["remote_device"] == "TV_original"


def test_backup_rejects_unknown_icon():
    bad = sample(raw=False)
    bad["icon"] = "not_an_icon"
    with pytest.raises(ValueError):
        backup.normalize_backup(document(bad))


def test_backup_rejects_untrusted_mdi_icon_value():
    bad = sample(raw=False)
    bad["icon_mdi"] = "mdi:<img>"
    with pytest.raises(ValueError, match="Invalid Material Design icon"):
        backup.normalize_backup(document(bad))
