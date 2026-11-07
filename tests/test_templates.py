"""Tests for the transport-neutral device and command template catalog."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "ir_studio"
spec = importlib.util.spec_from_file_location("ir_studio_templates_test", ROOT / "templates.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CATALOG = json.loads((ROOT / "presets.json").read_text(encoding="utf-8"))


def test_catalog_is_valid_and_contains_no_personal_remote_profiles():
    module.validate_template_catalog(CATALOG)
    ids = [item["id"] for cat in CATALOG["categories"] for item in cat["templates"]]
    names = [label for cat in CATALOG["categories"] for item in cat["templates"]
             for label in item["labels"].values()]
    assert "projector" in ids
    assert any(name == "Projector" for name in names)
    assert not any(name in names for name in ("TCL", "Hisense"))
    projector = module.build_template_buttons(CATALOG, "projector", "ru")
    # "Projector" identifies a device type, not a real Tuya IR key library.
    assert projector == []
    assert len(ids) >= 15


def test_every_template_command_is_resolvable_and_has_bilingual_labels():
    for cat in CATALOG["categories"]:
        for item in cat["templates"]:
            buttons = module.build_template_buttons(CATALOG, item["id"], "ru")
            assert len(buttons) == len(item["buttons"])
            assert all(button["status"] == "pending" and not button["verified"] for button in buttons)
            assert all(button["remote_name"] in {v["key"] for v in CATALOG["commands"].values()} for button in buttons)
            assert all(button["name"] for button in buttons)


def test_template_only_creates_button_scaffold_not_device_metadata():
    buttons = module.build_template_buttons(CATALOG, "tv_standard", "en")
    assert buttons[0]["remote_name"] == "Power"
    assert buttons[0]["name"] == "POWER"
    assert all("template_id" not in button and "device_type" not in button for button in buttons)


def test_button_sets_are_deduplicated_and_localized():
    buttons = module.build_button_set(CATALOG, ["power", "climate", "audio"], "ru")
    keys = [button["remote_name"] for button in buttons]
    assert len(keys) == len(set(key.casefold() for key in keys))
    assert any(button["name"] == "POWER" for button in buttons)
    assert any(button["name"] == "VOL +" for button in buttons)
    assert sum(button["remote_name"].casefold() == "power" for button in buttons) == 1
    singles = module.build_command_buttons(CATALOG, ["power", "volume_up"], "ru")
    assert [button["name"] for button in singles] == ["POWER", "VOL +"]
    power_set = next(item for item in CATALOG["button_sets"] if item["id"] == "power")
    assert power_set["labels"]["ru"] == "Включение и выключение"
    assert CATALOG["commands"]["power"]["key"] == "Power"  # stable learned-code identity


def test_unknown_template_and_set_are_rejected():
    import pytest
    with pytest.raises(ValueError):
        module.build_template_buttons(CATALOG, "not-a-template", "en")
    with pytest.raises(ValueError):
        module.build_button_set(CATALOG, ["not-a-set"], "en")
    with pytest.raises(ValueError):
        module.build_command_buttons(CATALOG, ["not-a-command"], "en")


def test_catalog_has_unique_remote_keys_and_clear_lighting_labels():
    keys = [item["key"].casefold() for item in CATALOG["commands"].values()]
    assert len(keys) == len(set(keys))

    templates = {
        item["id"]: item
        for category in CATALOG["categories"]
        for item in category["templates"]
    }
    white_lamp = templates["white_dimmer"]
    assert white_lamp["labels"]["ru"] == "Светильник"
    assert "яркость" in white_lamp["descriptions"]["ru"]
    lamp = templates["lamp"]
    assert lamp["labels"]["ru"] == "Лампа"
    assert lamp["id"] != white_lamp["id"]
    assert "ИК-пультом" in lamp["descriptions"]["ru"]

    assert len(templates) == 24
    assert sum(len(item["buttons"]) for item in templates.values()) == 212



def test_compact_starter_templates_keep_full_command_library_available():
    templates = {
        item["id"]: item
        for category in CATALOG["categories"]
        for item in category["templates"]
    }
    # Near-identical variants are intentionally combined; all actual IR
    # commands remain available through separate button sets.
    assert "satellite_receiver" not in templates
    assert "iptv_receiver" not in templates
    assert "hifi_cd" not in templates
    assert max(len(t["buttons"]) for t in templates.values()) <= 16
    assert len(CATALOG["commands"]) == 164
    assert len(CATALOG["button_sets"]) == 19
    assert len(module.build_button_set(CATALOG, ["numeric_keypad"], "en")) == 11
    assert len(module.build_button_set(CATALOG, ["media_playback"], "en")) == 11
    # Compact templates are a scaffold: never include learning results/raw IR.
    assert all("raw_code" not in t and "code" not in t for t in templates.values())





def test_startup_migrates_only_unused_cloud_placeholders():
    runtime = (ROOT / "__init__.py").read_text(encoding="utf-8")
    templates = (ROOT / "templates.py").read_text(encoding="utf-8")
    assert "recover_empty_account_profiles" not in runtime
    assert "recover_empty_account_profiles" not in templates
    assert "account_template_id" not in runtime
    loading = runtime.split("async def load(self):", 1)[1].split(
        "async def save(self):", 1
    )[0]
    assert "clean_cloud_placeholders" in loading
    assert "if removed or empty:" in loading
    assert 'await self.storage.async_save({"profiles": self.profiles})' in loading
    assert "template_id" not in loading or "build_template_buttons" not in loading




def test_all_library_buttons_english_and_legacy_rename_exact_match():
    assert all(item["labels"]["en"] == item["labels"]["ru"]
               for item in CATALOG["commands"].values())
    from copy import deepcopy
    profile = {"id": "p", "buttons": [
        {"id": "a", "name": "Вкл/Выкл", "remote_name": "Power",
         "status": "verified", "verified": True, "origin": "user_template"},
        {"id": "b", "name": "Громкость +", "remote_name": "Volume+",
         "status": "stored", "verified": False, "origin": "user_template"},
        {"id": "c", "name": "Моя громкость", "remote_name": "Volume-",
         "origin": "user_template", "verified": True},
        {"id": "d", "name": "Вкл/Выкл", "remote_name": "Power",
         "origin": "manual", "verified": True},
    ]}
    before = deepcopy(profile)
    assert module.upgrade_library_button_labels([profile], CATALOG) == 2
    assert [b["name"] for b in profile["buttons"]] == [
        "POWER", "VOL +", "Моя громкость", "Вкл/Выкл"]
    for updated, original in zip(profile["buttons"], before["buttons"]):
        assert {k: v for k, v in updated.items() if k != "name"} == {
            k: v for k, v in original.items() if k != "name"}
    assert module.upgrade_library_button_labels([profile], CATALOG) == 0


def test_legacy_migration_avoids_duplicate_visible_caption():
    buttons = [{"name": "Вкл/Выкл", "remote_name": "Power", "origin": "user_template"},
               {"name": "Power", "remote_name": "PowerOn", "origin": "manual"}]
    assert module.upgrade_library_button_labels([{"buttons": buttons}], CATALOG) == 0
    assert buttons[0]["name"] == "Вкл/Выкл"


def test_library_covers_every_defined_command_without_missing_keys():
    commands = set(CATALOG["commands"])
    listed = {key for group in CATALOG["button_sets"] for key in group["buttons"]}
    assert listed == commands
    assert len(commands) == 164
    assert len({item["id"] for item in CATALOG["button_sets"]}) == 19
    keys = [item["key"].casefold() for item in CATALOG["commands"].values()]
    assert len(set(keys)) == len(keys)
    labels = [item["labels"]["en"] for item in CATALOG["commands"].values()]
    assert len(set(labels)) == len(labels)
    assert all(item["labels"]["ru"] == item["labels"]["en"]
               for item in CATALOG["commands"].values())
    assert CATALOG["commands"]["volume_down"]["labels"]["en"] == "VOL -"
    assert CATALOG["commands"]["channel_down"]["labels"]["en"] == "CH -"


def test_legacy_english_minus_is_updated_without_changing_remote_code_identity():
    p = {"buttons": [
        {"id": "b1", "origin": "user_template", "remote_name": "Volume-",
         "name": "VOL −", "status": "stored", "verified": True},
        {"id": "b2", "origin": "manual", "remote_name": "Channel-",
         "name": "CH −", "status": "verified", "verified": True},
    ]}
    assert module.upgrade_library_button_labels([p], CATALOG) == 1
    assert p["buttons"][0] == {
        "id": "b1", "origin": "user_template", "remote_name": "Volume-",
        "name": "VOL -", "status": "stored", "verified": True,
    }
    assert p["buttons"][1]["name"] == "CH −"
    assert module.upgrade_library_button_labels([p], CATALOG) == 0


def test_command_labels_uppercase_are_compact_and_new_keys_pending():
    commands = CATALOG["commands"]
    assert len(commands) == 164
    assert all(value["labels"]["en"] == value["labels"]["ru"]
               and value["labels"]["en"] == value["labels"]["en"].upper()
               and len(value["labels"]["en"]) <= 16
               for value in commands.values())
    assert {"mode", "rgb", "rgb_mode", "flash", "strobe", "fade", "smooth",
            "hdmi_1", "keystone_up", "subwoofer_up"} <= set(commands)
    assert commands["mode"]["key"] == "Mode"
    items = module.build_command_buttons(CATALOG, ["mode", "rgb", "flash"])
    assert [x["name"] for x in items] == ["MODE", "RGB", "FLASH"]
    assert [x["remote_name"] for x in items] == ["Mode", "RGB", "Flash"]
    assert all(x["status"] == "pending" and not x["verified"] for x in items)


def test_previous_generated_names_upgrade_without_changing_learned_keys():
    from copy import deepcopy
    profile = {"buttons": [
        {"id": "a", "name": "Power", "remote_name": "Power",
         "status": "stored", "verified": True, "origin": "user_template"},
        {"id": "b", "name": "Mode", "remote_name": "Mode",
         "status": "pending", "verified": False, "origin": "user_template"},
        {"id": "c", "name": "Custom name", "remote_name": "Mode",
         "status": "stored", "verified": False, "origin": "user_template"},
        {"id": "d", "name": "My manual", "remote_name": "Mode",
         "status": "stored", "verified": False, "origin": "manual"},
    ]}
    old = deepcopy(profile["buttons"])
    assert module.upgrade_library_button_labels([profile], CATALOG) == 2
    assert [b["name"] for b in profile["buttons"]] == [
        "POWER", "MODE", "Custom name", "My manual"]
    for a, b in zip(profile["buttons"], old):
        assert {k: v for k, v in a.items() if k != "name"} == {
            k: v for k, v in b.items() if k != "name"}
    assert module.upgrade_library_button_labels([profile], CATALOG) == 0
