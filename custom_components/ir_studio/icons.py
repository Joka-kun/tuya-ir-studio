"""Single-source, presentation-only IR remote icon registry."""
from __future__ import annotations

import re

ICON_GROUPS = frozenset(("video", "audio", "climate", "lighting", "home", "appliance"))


def validate_icon_catalog(data: dict) -> list[dict]:
    """Validate the shipped icon catalogue; never use icon IDs as IR namespaces."""
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("Unsupported IR Studio icon catalog")
    items = data.get("icons")
    if not isinstance(items, list) or len(items) != 200:
        raise ValueError("Expected exactly 200 remote icons")
    ids, glyphs = set(), set()
    for icon in items:
        if not isinstance(icon, dict):
            raise ValueError("Invalid icon")
        key, glyph = icon.get("id"), icon.get("mdi")
        labels = icon.get("labels")
        if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            raise ValueError("Invalid icon ID")
        if not isinstance(glyph, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", glyph):
            raise ValueError("Invalid MDI icon name")
        if key in ids or glyph in glyphs:
            raise ValueError("Duplicate remote icon ID or glyph")
        if icon.get("group") not in ICON_GROUPS:
            raise ValueError("Invalid icon group")
        if not isinstance(labels, dict) or not all(
            isinstance(labels.get(lang), str) and labels[lang].strip()
            for lang in ("en", "ru")
        ):
            raise ValueError("Missing translated icon label")
        ids.add(key)
        glyphs.add(glyph)
    if not {"tv_standard", "projector", "lamp", "blank_remote"} <= ids:
        raise ValueError("Legacy icon compatibility is missing")
    return items


def validate_icon_id(icons: list[dict], value: str) -> str:
    if not isinstance(value, str) or value not in {icon["id"] for icon in icons}:
        raise ValueError("Неизвестная иконка пульта")
    return value
