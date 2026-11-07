"""Ensure all 200 remote icons are valid, nonduplicated, and display-only."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "ir_studio"
spec = importlib.util.spec_from_file_location("studio_icons_test", ROOT / "icons.py")
icons = importlib.util.module_from_spec(spec)
spec.loader.exec_module(icons)
CATALOG = json.loads((ROOT / "icon_catalog.json").read_text(encoding="utf-8"))


def test_catalog_exactly_200_and_no_duplicates():
    items = icons.validate_icon_catalog(CATALOG)
    assert len(items) == 200
    assert len({item["id"] for item in items}) == 200
    assert len({item["mdi"] for item in items}) == 200
    assert all(item["mdi"] for item in items)
    assert icons.validate_icon_id(items, "lamp") == "lamp"


def test_legacy_profiles_icons_are_still_valid():
    legacy = ("tv_standard", "tv_smart", "projector", "stb_general",
              "streaming_player", "dvd_bluray", "dvr_vcr", "soundbar",
              "av_receiver", "split_ac", "portable_ac", "floor_tower_fan",
              "ceiling_fan", "electric_heater", "air_purifier", "humidifier",
              "dehumidifier", "white_dimmer", "lamp", "rgb_controller",
              "camera_shutter", "robot_vacuum_ir", "water_heater_ir",
              "blank_remote")
    current = {x["id"] for x in CATALOG["icons"]}
    assert set(legacy) <= current


def test_invalid_icons_rejected():
    import copy
    import pytest
    original = icons.validate_icon_catalog(CATALOG)
    for bad_id in ("not_registered", "mdi:television", "<script>"):
        with pytest.raises(ValueError):
            icons.validate_icon_id(original, bad_id)
    broken = copy.deepcopy(CATALOG)
    broken["icons"][1]["mdi"] = broken["icons"][0]["mdi"]
    with pytest.raises(ValueError):
        icons.validate_icon_catalog(broken)
