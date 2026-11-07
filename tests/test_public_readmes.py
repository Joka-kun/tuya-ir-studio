"""Public GitHub presentation stays clean and correctly localized."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGUAGE_READMES = (
    "README.md", "README_RU.md", "README_DE.md",
    "README_FR.md", "README_ES.md", "README_ZH.md",
)


def test_language_switchers_are_real_links_and_have_targets():
    for name in LANGUAGE_READMES:
        text = (ROOT / name).read_text(encoding="utf-8")
        for lang in LANGUAGE_READMES:
            assert f'<a href="{lang}">' in text, (name, lang)
            assert (ROOT / lang).is_file()
        assert not re.search(r"\[(English|Русский|Deutsch)\]\(README", text), name
        for artwork in ("assets/banner.svg", "assets/workflow.svg"):
            assert artwork in text
            assert (ROOT / artwork).is_file()
        # Public landing pages describe functionality, not arbitrary release
        # numbers. The version is in manifest / Releases / changelog.
        assert not re.search(r"\b(?:v)?\d+\.\d+\.\d+\b", text), name


def test_russian_library_has_toggle_name_but_same_remote_code():
    catalog = json.loads((ROOT / "custom_components/ir_studio/presets.json")
                         .read_text(encoding="utf-8"))
    assert catalog["commands"]["power"]["key"] == "Power"
    assert catalog["commands"]["power"]["labels"]["ru"] == "Power"
    assert catalog["commands"]["power"]["legacy_ru"] == "Вкл/Выкл"
    power_group = next(x for x in catalog["button_sets"] if x["id"] == "power")
    assert power_group["labels"]["ru"] == "Включение и выключение"


def test_readmes_do_not_advertise_removed_cloud_button_import():
    ru = (ROOT / "README_RU.md").read_text(encoding="utf-8")
    en = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Экспериментальный импорт кнопок Smart Life удалён" in ru
    assert "cloud button imports have been removed" in en
    assert "для настройки шлюза" in ru
    assert "onboarding the physical hub" in en


def test_qr_onboarding_and_privately_cached_auth_remain_supported():
    cloud = (ROOT / "custom_components/ir_studio/tuya_cloud.py").read_text()
    init = (ROOT / "custom_components/ir_studio/__init__.py").read_text()
    assert "async_restore_cloud_auth" in init
    assert "async_persist_cloud_auth" in cloud
    assert "async_get_devices" in cloud
    # Clean-up after reinstall removes speculative buttons, not credentials.
    assert "CLOUD_AUTH_STORE_KEY" in cloud
    legacy = (ROOT / "custom_components/ir_studio/legacy_cleanup.py").read_text()
    assert "CLOUD_AUTH_STORE_KEY" not in legacy
