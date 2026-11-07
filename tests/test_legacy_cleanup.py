"""v1.0 migration: legacy cloud placeholders never displace learned IR codes."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "custom_components" / "ir_studio" / "legacy_cleanup.py"
spec = importlib.util.spec_from_file_location("studio_cleanup_test", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_unverified_old_cloud_buttons_and_empty_profiles_are_removed():
    profiles = [{
        "id": "p1", "name": "Light_Table",
        "account_origin": "tuya_sharing_device_metadata",
        "account_ref": "old-ref",
        "buttons": [
            {"id": "a", "name": "BlueLight", "origin": "tuya_device_specification",
             "status": "pending", "verified": False},
            {"id": "b", "name": "PowerOn", "origin": "tuya_ir_remote_keys",
             "status": "pending", "verified": False},
        ],
    }, {
        "id": "p2", "name": "Manual", "buttons": [
            {"id": "c", "name": "Power", "origin": "user_template",
             "status": "pending", "verified": False},
        ],
    }]
    assert module.clean_cloud_placeholders(profiles, {}, {}) == (2, 1)
    assert [p["name"] for p in profiles] == ["Manual"]
    assert profiles[0]["buttons"][0]["name"] == "Power"
    assert module.clean_cloud_placeholders(profiles, {}, {}) == (0, 0)


def test_never_remove_learned_stored_or_verified_cloud_button():
    profile = {"id": "p", "name": "Preserved", "account_ref": "old",
               "account_origin": "tuya_sharing_device_metadata", "buttons": [
        {"id": "a", "status": "pending", "verified": False,
         "origin": "tuya_account_mapping"},
        {"id": "b", "status": "pending", "verified": False,
         "origin": "tuya_device_specification"},
        {"id": "c", "status": "stored", "verified": False,
         "origin": "tuya_device_mapping"},
        {"id": "d", "status": "pending", "verified": True,
         "origin": "tuya_ir_remote_keys"},
        {"id": "e", "status": "pending", "verified": False},
        {"id": "f", "status": "needs_check", "verified": False,
         "origin": "tuya_export_mapping"},
    ]}
    profiles = [profile]
    ir_codes = {"p/a": "original-learned"}
    native_codes = {"p/b": "native-learned"}
    assert module.clean_cloud_placeholders(profiles, ir_codes, native_codes) == (0, 0)
    assert profiles[0] is profile
    assert len(profile["buttons"]) == 6
    assert ir_codes["p/a"] == "original-learned"
    assert native_codes["p/b"] == "native-learned"


def test_partial_cloud_profile_keeps_edited_manual_buttons():
    p = {"id": "p", "name": "Light_Table",
         "account_ref": "ref", "account_origin": "tuya_sharing_device_metadata",
         "buttons": [
             {"id": "a", "origin": "tuya_device_specification",
              "status": "pending", "verified": False},
             {"id": "b", "name": "Favorite", "origin": "user_template",
              "status": "pending", "verified": False},
         ]}
    profiles = [p]
    assert module.clean_cloud_placeholders(profiles, {}, {}) == (1, 0)
    assert profiles[0] is p
    assert [x["name"] for x in p["buttons"]] == ["Favorite"]


def test_preexisting_empty_cloud_profile_is_never_silently_deleted():
    """An empty profile can be intentional, including after a user edit."""
    empty = {"id": "kept", "name": "Customized", "account_ref": "old-ref",
             "account_origin": "tuya_sharing_device_metadata", "buttons": []}
    imported = {"id": "dropped", "name": "Obsolete",
                "account_ref": "ref", "account_origin": "tuya_sharing_device_metadata",
                "buttons": [{"id": "x", "origin": "tuya_account_mapping",
                             "status": "pending", "verified": False}]}
    profiles = [empty, imported]
    assert module.clean_cloud_placeholders(profiles, {}, {}) == (1, 1)
    assert profiles == [empty]
    assert module.clean_cloud_placeholders(profiles, {}, {}) == (0, 0)


def test_orphaned_waveform_never_causes_its_profile_to_disappear():
    profile = {
        "id": "p", "name": "Recovered Remote",
        "account_ref": "legacy", "account_origin": "tuya_sharing_device_metadata",
        "buttons": [
            {"id": "placeholder", "origin": "tuya_ir_remote_keys",
             "status": "pending", "verified": False},
        ],
    }
    profiles = [profile]
    native_codes = {"p/previously_removed": "learned-waveform"}
    assert module.clean_cloud_placeholders(profiles, {}, native_codes) == (1, 0)
    assert profiles == [profile]
    assert profile["buttons"] == []
    assert native_codes["p/previously_removed"] == "learned-waveform"
