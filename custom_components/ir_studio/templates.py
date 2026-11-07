"""Validated, transport-neutral device and command templates."""
from __future__ import annotations

import uuid


def validate_template_catalog(catalog: dict) -> dict:
    if not isinstance(catalog, dict) or catalog.get("schema_version") != 2:
        raise ValueError("Unsupported template catalog schema")
    commands = catalog.get("commands")
    categories = catalog.get("categories")
    button_sets = catalog.get("button_sets")
    if not isinstance(commands, dict) or not isinstance(categories, list) or not isinstance(button_sets, list):
        raise ValueError("Invalid template catalog structure")
    for command_id, item in commands.items():
        if not isinstance(command_id, str) or not isinstance(item, dict):
            raise ValueError("Invalid command definition")
        if not isinstance(item.get("key"), str) or not item["key"].strip():
            raise ValueError(f"Invalid remote command key: {command_id}")
        _validate_labels(item.get("labels"), command_id)
    seen_templates = set()
    for cat in categories:
        if not isinstance(cat, dict) or not isinstance(cat.get("id"), str):
            raise ValueError("Invalid template category")
        _validate_labels(cat.get("labels"), cat["id"])
        templates = cat.get("templates")
        if not isinstance(templates, list):
            raise ValueError(f"Invalid templates in category: {cat['id']}")
        for item in templates:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise ValueError("Invalid device template")
            if item["id"] in seen_templates:
                raise ValueError(f"Duplicate template ID: {item['id']}")
            seen_templates.add(item["id"])
            _validate_labels(item.get("labels"), item["id"])
            _validate_commands(item.get("buttons"), commands, item["id"])
    seen_sets = set()
    for item in button_sets:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise ValueError("Invalid button set")
        if item["id"] in seen_sets:
            raise ValueError(f"Duplicate button set ID: {item['id']}")
        seen_sets.add(item["id"])
        _validate_labels(item.get("labels"), item["id"])
        _validate_commands(item.get("buttons"), commands, item["id"])
    return catalog


def _validate_labels(value, owner):
    if not isinstance(value, dict) or not all(isinstance(value.get(lang), str) and value[lang].strip() for lang in ("en", "ru")):
        raise ValueError(f"Missing English/Russian labels: {owner}")


def _validate_commands(buttons, commands, owner):
    if not isinstance(buttons, list) or len(buttons) > 200:
        raise ValueError(f"Invalid button list: {owner}")
    if len(buttons) != len(set(buttons)):
        raise ValueError(f"Duplicate command in template: {owner}")
    if any(command_id not in commands for command_id in buttons):
        raise ValueError(f"Unknown command in template: {owner}")


def _template_index(catalog):
    validate_template_catalog(catalog)
    return {item["id"]: item for cat in catalog["categories"] for item in cat["templates"]}


def _make_button(catalog, command_id, language):
    command = catalog["commands"][command_id]
    # Remote button captions use the universal English legends printed on
    # physical remotes. The code key is deliberately unchanged.
    return {
        "id": uuid.uuid4().hex,
        "name": command["labels"]["en"],
        "remote_name": command["key"],
        "status": "pending",
        "verified": False,
        # A library/template choice is user-selected; never claim this
        # command came from their saved Smart Life cloud remote.
        "origin": "user_template",
    }


def build_template_buttons(catalog, template_id, language="en"):
    template = _template_index(catalog).get(template_id)
    if template is None:
        raise ValueError("Шаблон устройства не найден")
    return [_make_button(catalog, command_id, language) for command_id in template["buttons"]]


def build_command_buttons(catalog, command_ids, language="en"):
    validate_template_catalog(catalog)
    if not isinstance(command_ids, list) or not command_ids or len(command_ids) > 200:
        raise ValueError("Выбери одну или несколько команд")
    commands = catalog["commands"]
    if any(command_id not in commands for command_id in command_ids):
        raise ValueError("Неизвестная команда в библиотеке")
    result = []
    seen_keys = set()
    for command_id in command_ids:
        key = commands[command_id]["key"].casefold()
        if key in seen_keys:
            continue
        seen_keys.add(key)
        result.append(_make_button(catalog, command_id, language))
    return result


def build_button_set(catalog, set_ids, language="en"):
    validate_template_catalog(catalog)
    if not isinstance(set_ids, list) or not set_ids or len(set_ids) > 20:
        raise ValueError("Выбери один или несколько наборов команд")
    index = {item["id"]: item for item in catalog["button_sets"]}
    if len(set(set_ids)) != len(set_ids) or any(set_id not in index for set_id in set_ids):
        raise ValueError("Неизвестный или повторяющийся набор команд")
    command_ids = [command_id for set_id in set_ids for command_id in index[set_id]["buttons"]]
    seen = []
    for command_id in command_ids:
        if command_id not in seen:
            seen.append(command_id)
    return build_command_buttons(catalog, seen, language)


def upgrade_library_button_labels(profiles: list[dict], catalog: dict) -> int:
    """Migrate only unchanged original library-generated command captions.

    The visible caption may change, but neither remote_name nor any stored
    IR code / verification metadata is ever touched. User-created or renamed
    labels are protected by origin and exact-match checks.
    """
    commands = catalog.get("commands", {}) if isinstance(catalog, dict) else {}
    by_key = {item["key"]: item for item in commands.values()
              if isinstance(item, dict) and isinstance(item.get("key"), str)}
    renamed = 0
    for profile in profiles:
        buttons = profile.get("buttons", [])
        for button in buttons:
            if button.get("origin") != "user_template":
                continue
            command = by_key.get(button.get("remote_name"))
            if not command:
                continue
            historical = {command.get("legacy_ru"), command.get("legacy_en")}
            historical.discard(None)
            new = command.get("labels", {}).get("en")
            if not new or button.get("name") not in historical:
                continue
            # Do not create confusing duplicate visible names.
            if any(other is not button and other.get("name", "").casefold() == new.casefold()
                   for other in buttons):
                continue
            button["name"] = new
            renamed += 1
    return renamed
