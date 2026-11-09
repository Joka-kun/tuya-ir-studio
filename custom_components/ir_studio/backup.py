"""Portable, versioned IR Studio profile backups. No network or HA imports here.

The transport-specific IR waveforms may not be available for every remote backend.
Backup application is staged and validated before updating the active Store.
"""
from __future__ import annotations

import copy
import uuid
import json
from pathlib import Path

from .utils import clean_label, remote_entity_id, validate_raw_b64
from .native_transport import validate_code
from .icons import validate_icon_catalog, validate_icon_id

FORMAT = "tuya-ir-studio-backup"
MAX_PROFILES = 24
MAX_BUTTONS = 200
STATUSES = {"pending", "needs_check", "stored", "verified"}


def normalize_backup(document: dict, *, valid_icons=None) -> list[dict]:
    if not isinstance(document, dict):
        raise ValueError("Backup must be a JSON object")
    kind = document.get("format")
    if kind == FORMAT and document.get("format_version") in (2, 3):
        source = document.get("profiles")
    elif kind == "ir-studio-backup" and document.get("format_version") == 1:
        source = document.get("profiles")
    elif kind == "ir-studio-profile" and document.get("format_version") == 1:
        source = [document.get("profile")]
    else:
        raise ValueError("Unsupported backup format or version")
    if not isinstance(source, list) or len(source) > MAX_PROFILES:
        raise ValueError("Backup contains an invalid number of profiles")
    if valid_icons is None:
        # Standalone backup utilities/tests only. Home Assistant WebSocket
        # callers pass the cached runtime catalog, avoiding blocking disk I/O.
        valid_icons = validate_icon_catalog(json.loads(
            Path(__file__).with_name("icon_catalog.json").read_text(encoding="utf-8")
        ))
    normalized = []
    seen_ids, seen_names = set(), set()
    for item in source:
        if not isinstance(item, dict):
            raise ValueError("Invalid profile object")
        profile_id = item.get("id")
        if not isinstance(profile_id, str) or not 1 <= len(profile_id) <= 80:
            raise ValueError("Invalid profile ID")
        name = clean_label(item.get("name"), limit=64)
        key = name.casefold()
        if profile_id in seen_ids or key in seen_names:
            raise ValueError("Duplicate profile ID or name in backup")
        seen_ids.add(profile_id); seen_names.add(key)
        raw_buttons = item.get("buttons")
        if not isinstance(raw_buttons, list) or len(raw_buttons) > MAX_BUTTONS:
            raise ValueError("Invalid button list")
        profile = {
            "id": profile_id,
            "name": name,
            "remote_device": clean_label(item.get("remote_device", name), limit=64),
            "remote_entity": remote_entity_id(item.get("remote_entity")),
            "buttons": [],
        }
        if "icon" in item:
            profile["icon"] = validate_icon_id(valid_icons, item["icon"])
        if "icon_mdi" in item:
            from .icon_mdi import validate_mdi_icon
            profile["icon_mdi"] = validate_mdi_icon(item["icon_mdi"])
        seen_button_ids, seen_button_names = set(), set()
        for b in raw_buttons:
            if not isinstance(b, dict) or not isinstance(b.get("id"), str) or not 1 <= len(b["id"]) <= 80:
                raise ValueError("Invalid button ID")
            label = clean_label(b.get("name"))
            remote_name = clean_label(b.get("remote_name", label))
            if b["id"] in seen_button_ids or label.casefold() in seen_button_names:
                raise ValueError("Duplicate button ID or label")
            seen_button_ids.add(b["id"]); seen_button_names.add(label.casefold())
            # A foreign backend cannot be assumed to have learned these commands.
            button = {"id": b["id"], "name": label, "remote_name": remote_name,
                      "status": "needs_check" if b.get("status") in ("verified", "stored", "needs_check") else "pending",
                      "verified": False}
            if "raw_ir" in b:
                code = b["raw_ir"]
                button["raw_ir"] = validate_raw_b64(code)
            if "tuya_code" in b:
                button["tuya_code"] = validate_code(b["tuya_code"])
            if "raw_ir" in b and "tuya_code" in b:
                raise ValueError("Ambiguous IR payload formats")
            profile["buttons"].append(button)
        normalized.append(profile)
    return normalized


def make_import_plan(existing: list[dict], backup: dict, selected_ids: list[str], strategy: str, *, valid_icons=None, remote_bindings: dict[str, str] | None = None) -> tuple[list[dict], dict]:
    """Compute changes without mutating existing profiles.

    skip: add only new profiles, merge: add unmatched buttons to existing
    profiles, replace: replace only profiles explicitly selected by the user.
    Newly added profile UUIDs are regenerated if they clash with other profiles.
    """
    if strategy not in {"skip", "merge", "replace"}:
        raise ValueError("Unknown conflict strategy")
    if not isinstance(selected_ids, list) or not selected_ids or len(selected_ids) > MAX_PROFILES:
        raise ValueError("Select at least one profile")
    if not all(isinstance(v, str) for v in selected_ids) or len(set(selected_ids)) != len(selected_ids):
        raise ValueError("Invalid selection")
    source = normalize_backup(backup, valid_icons=valid_icons)
    by_id = {p["id"]: p for p in source}
    if any(s not in by_id for s in selected_ids):
        raise ValueError("Selected profile is absent from backup")
    # Binding is a live HA entity reference, not an IR code namespace.
    # Never modify remote_device, remote_name or the waveform during remapping.
    remote_bindings = remote_bindings or {}
    if not isinstance(remote_bindings, dict) or any(
        key not in selected_ids or not isinstance(value, str)
        for key, value in remote_bindings.items()
    ):
        raise ValueError("Invalid selected remote bindings")
    target = copy.deepcopy(existing)
    changes = {"added_profiles": [], "merged_profiles": [], "replaced_profiles": [], "skipped_profiles": [],
               "added_buttons": 0, "raw_codes": 0}
    for sid in selected_ids:
        incoming = copy.deepcopy(by_id[sid])
        selected_remote = remote_bindings.get(sid)
        if selected_remote:
            incoming["remote_entity"] = remote_entity_id(selected_remote)
        raw = 0
        for button in incoming["buttons"]:
            if "raw_ir" in button or "tuya_code" in button:
                raw += 1
        found = next((p for p in target if p["id"] == sid), None)
        if found is None:
            found = next((p for p in target if p["name"].casefold() == incoming["name"].casefold()), None)
        if found is None:
            if len(target) >= MAX_PROFILES:
                raise ValueError("Maximum number of profiles exceeded")
            if any(p["id"] == incoming["id"] for p in target):
                incoming["id"] = uuid.uuid4().hex
            target.append(incoming)
            changes["added_profiles"].append(incoming["name"])
            changes["added_buttons"] += len(incoming["buttons"])
            changes["raw_codes"] += raw
        elif strategy == "skip":
            changes["skipped_profiles"].append(incoming["name"])
        elif strategy == "replace":
            # Preserve the active HA profile ID for registry compatibility.
            incoming["id"] = found["id"]
            target[target.index(found)] = incoming
            changes["replaced_profiles"].append(incoming["name"])
            changes["raw_codes"] += raw
        else:
            # Merge may explicitly rebind the executor while retaining button
            # keys, waveform namespaces, order and HA profile identity.
            if selected_remote:
                found["remote_entity"] = incoming["remote_entity"]
            existing_ids = {b["id"] for b in found["buttons"]}
            existing_labels = {b["name"].casefold() for b in found["buttons"]}
            for b in incoming["buttons"]:
                if b["id"] in existing_ids or b["name"].casefold() in existing_labels:
                    continue
                if len(found["buttons"]) >= MAX_BUTTONS:
                    raise ValueError("Maximum number of buttons exceeded")
                found["buttons"].append(b)
                changes["added_buttons"] += 1
                if "raw_ir" in b or "tuya_code" in b:
                    changes["raw_codes"] += 1
            changes["merged_profiles"].append(incoming["name"])
    return target, changes


def strip_export_profile(profile: dict, read_code=None) -> tuple[dict, int]:
    """Return safe metadata + optional raw code; never expose HA auth or secrets."""
    item = {k: copy.deepcopy(profile[k]) for k in ("id", "name", "remote_entity")}
    item["remote_device"] = profile.get("remote_device", profile["name"])
    if "icon" in profile:
        item["icon"] = profile["icon"]
    if "icon_mdi" in profile:
        item["icon_mdi"] = profile["icon_mdi"]
    item["buttons"] = []
    raws = 0
    for button in profile["buttons"]:
        b = {"id": button["id"], "name": button["name"],
             "remote_name": button.get("remote_name", button["name"]),
             "status": button.get("status", "pending"),
             "verified": bool(button.get("verified"))}
        if read_code:
            code = read_code(profile, button)
            if isinstance(code, dict) and code.get("format") == "tuya_dp202":
                try:
                    b["tuya_code"] = validate_code(code.get("code"))
                    raws += 1
                except ValueError:
                    pass
            elif isinstance(code, str):
                try:
                    b["raw_ir"] = validate_raw_b64(code)
                    raws += 1
                except ValueError:
                    pass
        item["buttons"].append(b)
    return item, raws
