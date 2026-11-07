"""Release and localization contracts for the public GitHub repository."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "ir_studio"


def _keys(mapping: dict, prefix: str = "") -> set[str]:
    result = set()
    for key, value in mapping.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            result.update(_keys(value, name + "."))
        else:
            result.add(name)
    return result


def test_version_is_consistent_between_manifest_frontend_cache_and_changelog():
    version = json.loads((INTEGRATION / "manifest.json").read_text())["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)
    const = (INTEGRATION / "const.py").read_text()
    assert f'FRONTEND_VERSION = "{version}"' in const
    changelog = (ROOT / "CHANGELOG.md").read_text()
    assert f"## {version} " in changelog


def test_native_options_flow_has_complete_english_and_russian_labels():
    base = json.loads((INTEGRATION / "strings.json").read_text())["options"]
    expected = _keys(base)
    assert len(expected) > 50
    for lang in ("en", "ru"):
        translated = json.loads(
            (INTEGRATION / "translations" / f"{lang}.json").read_text()
        )["options"]
        assert _keys(translated) == expected, lang
        assert all(isinstance(v, str) and v.strip()
                   for v in _values(translated))


def _values(item: dict):
    for value in item.values():
        if isinstance(value, dict):
            yield from _values(value)
        else:
            yield value


def test_main_readmes_do_not_advertise_unverified_cloud_ir_import_or_release():
    for file in ("README.md", "README_RU.md"):
        text = (ROOT / file).read_text()
        assert "tuya-ir-studio" in text
        assert "button.press" in text or "button" in text
        assert "remote.send_command" in text or "`remote`" in text
        assert not re.search(r"\bv\d+\.\d+\.\d+\b", text)
    assert "hardware acceptance" in (ROOT / "ROADMAP.md").read_text().lower()


def test_no_external_images_or_scripts_in_repository_svg_artwork():
    for filename in ("banner.svg", "workflow.svg"):
        text = (ROOT / "assets" / filename).read_text(encoding="utf-8")
        assert text.lstrip().startswith("<svg ")
        assert not re.search(r"<(?:script|foreignObject|iframe)\b", text, re.I)
        assert not re.search(r"(?:href|src)=[\"'](?:https?:|data:|//)", text, re.I)



def test_verified_release_is_non_destructive_and_sha_bound():
    """A new baseline must never delete other releases or publish untested code."""
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text()
    assert "github.event.workflow_run.event == 'push'" in workflow
    assert 'if [[ "$current" != "$SHA" ]]' in workflow
    assert '"Unit tests and syntax" "Hassfest" "Validate HACS"' in workflow
    assert '"$tag" --repo "$REPO" --target "$SHA"' in workflow
    assert 'actual_tag_sha=$(gh api "repos/${REPO}/git/ref/tags/${tag}"' in workflow
    assert 'if [[ "$actual_tag_sha" != "$SHA" ]]' in workflow
    assert '--method DELETE' not in workflow
    assert '--cleanup-tag' not in workflow
