"""Authenticated IR Studio UI operations over Home Assistant's own WebSocket.

All mutations are admin-only; the panel does not persist keys, make direct Tuya
network requests, or pretend that an HA API acknowledgment proves IR emission.
"""
from __future__ import annotations

import asyncio
import copy
import logging
import time
import uuid
from datetime import datetime, timezone

from .backup import FORMAT, make_import_plan, normalize_backup, strip_export_profile

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import Context
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .utils import clean_label, remote_entity_id, reorder_buttons, validate_raw_b64
from .templates import build_button_set, build_command_buttons, build_template_buttons
from .icons import validate_icon_id
from .native_transport import validate_code
from .ir_file_import import parse_flipper_ir

_LOGGER = logging.getLogger(__name__)


def _rt(hass):
    return hass.data[DOMAIN]


def _remove_profile_payloads(runtime, profile_id):
    """Remove only IR Studio-owned payloads for a deleted/replaced profile."""
    prefix = f"{profile_id}/"
    for store in (runtime.ir_codes, runtime.native_codes):
        for key in tuple(store):
            if key.startswith(prefix):
                store.pop(key, None)


def _remove_button_payloads(runtime, profile_id, button_id):
    """Remove only IR Studio-owned payloads for one deleted command."""
    key = f"{profile_id}/{button_id}"
    runtime.ir_codes.pop(key, None)
    runtime.native_codes.pop(key, None)


def _fail(connection, msg, exc):
    # Prevent any accidentally sensitive device response from being surfaced.
    description = str(exc)
    if len(description) > 180:
        description = description[:180] + "…"
    connection.send_error(msg["id"], "invalid_request", description)


def _source(hass, entity_id):
    item = er.async_get(hass).async_get(entity_id)
    return (item.platform or "unknown") if item else "unknown"


def _known_code(hass, profile, button):
    """Check supported local stores; HA service success is not physical proof."""
    runtime = hass.data.get(DOMAIN)
    if runtime:
        native = runtime.native_remotes.get(profile["remote_entity"])
        if native:
            return native.has_code(profile.get("remote_device", profile["name"]),
                                   button.get("remote_name", button["name"]))
    entity = er.async_get(hass).async_get(profile["remote_entity"])
    if not entity or entity.platform != "tuya_ir" or not entity.config_entry_id:
        return None
    rt = hass.data.get("tuya_ir", {}).get(entity.config_entry_id)
    if rt is None or not hasattr(rt, "store"):
        return None
    # A hub remote namespaces learned codes with 'device' = profile name.
    # Display labels may be renamed; retain the original CodeStore keys.
    device_key = profile.get("remote_device", profile["name"])
    command_key = button.get("remote_name", button["name"])
    return bool(rt.store.get(device_key, command_key))


@websocket_api.websocket_command({vol.Required("type"): "ir_studio/get"})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_get(hass, connection, msg):
    runtime = _rt(hass)
    profiles = []
    for profile in runtime.profiles:
        p = dict(profile)
        p["buttons"] = []
        p["source"] = _source(hass, profile["remote_entity"])
        for btn in profile["buttons"]:
            b = dict(btn)
            known = _known_code(hass, profile, btn)
            b["code_in_tuya_ir_store"] = known
            b["code_in_local_store"] = known
            p["buttons"].append(b)
        profiles.append(p)
    connection.send_result(msg["id"], {
        "profiles": profiles,
        "presets": {key: len(value) for key, value in runtime.presets.items()},
        "template_catalog": runtime.template_catalog,
        "icons": runtime.icons,
        "jobs": list(runtime.jobs.values())[-12:],
    })


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/ir_file_preview",
    vol.Required("profile_id"): str,
    vol.Required("content"): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_ir_file_preview(hass, connection, msg):
    """Review supported IR waveforms; the WebSocket reply contains NO raw pulses."""
    runtime = _rt(hass)
    try:
        profile = runtime.find_profile(msg["profile_id"])
        if not runtime.native_remotes.get(profile["remote_entity"]):
            raise ValueError("Нужен нативный локальный Remote IR Studio")
        parsed = parse_flipper_ir(msg["content"])
        connection.send_result(msg["id"], {
            "supported_names": parsed["supported_names"],
            "unsupported": parsed["unsupported"],
            "total": parsed["total"],
        })
    except ValueError as exc:
        _fail(connection, msg, exc)


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/ir_file_import",
    vol.Required("profile_id"): str,
    vol.Required("content"): str,
    vol.Required("mappings"): [{
        vol.Required("source_name"): str,
        vol.Required("button_id"): str,
    }],
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_ir_file_import(hass, connection, msg):
    """Fill imported button placeholders with *real* offline infrared signals.

    Mappings are explicit profile button IDs, never guessed from device names.
    Local learned / verified codes are immutable. No remote.send_command or
    cloud call is made as a side effect of importing the file.
    """
    runtime = _rt(hass)
    try:
        mappings = msg["mappings"]
        if not 1 <= len(mappings) <= 100:
            raise ValueError("Выбери от 1 до 100 кодов")
        sources = [item["source_name"] for item in mappings]
        buttons = [item["button_id"] for item in mappings]
        if len(set(sources)) != len(sources) or len(set(buttons)) != len(buttons):
            raise ValueError("Один исходный код должен соответствовать одной кнопке")
        parsed = parse_flipper_ir(msg["content"])
        if any(source not in parsed["codes"] for source in sources):
            raise ValueError("В файле нет выбранного настоящего ИК-кода")

        async with runtime.lock:
            profile = runtime.find_profile(msg["profile_id"])
            native = runtime.native_remotes.get(profile["remote_entity"])
            if native is None:
                raise ValueError("Локальный IR Studio Remote недоступен")
            button_map = {button["id"]: button for button in profile["buttons"]}
            if any(button_id not in button_map for button_id in buttons):
                raise ValueError("Состав профиля изменился: открой импорт заново")

            original_codes = dict(runtime.native_codes)
            original_profiles = copy.deepcopy(runtime.profiles)
            imported, preserved = 0, 0
            try:
                for entry in mappings:
                    button = button_map[entry["button_id"]]
                    device_key = profile.get("remote_device", profile["name"])
                    command_key = button.get("remote_name", button["name"])
                    if (button.get("verified")
                            or f"{profile['id']}/{button['id']}" in runtime.native_codes
                            or native.has_code(device_key, command_key)):
                        preserved += 1
                        continue
                    key = f"{profile['id']}/{button['id']}"
                    runtime.native_codes[key] = validate_code(
                        parsed["codes"][entry["source_name"]]
                    )
                    button["status"] = "stored"
                    button["verified"] = False
                    button["origin"] = button.get("origin") or "file_waveform"
                    button["code_origin"] = "flipper_ir_profile"
                    imported += 1
                if imported:
                    await runtime.save()
            except Exception:
                runtime.profiles[:] = original_profiles
                runtime.native_codes.clear()
                runtime.native_codes.update(original_codes)
                try:
                    await runtime.save()
                except Exception:
                    _LOGGER.warning("IR file import rollback could not persist")
                raise
        connection.send_result(msg["id"], {
            "codes_imported": imported,
            "existing_preserved": preserved,
            "unmapped": len(parsed["codes"]) - len(mappings),
            "unsupported": len(parsed["unsupported"]),
            "needs_physical_test": True,
        })
    except ValueError as exc:
        _fail(connection, msg, exc)
    except Exception as exc:
        _LOGGER.warning("IR file import failed (%s)", type(exc).__name__)
        connection.send_error(msg["id"], "import_failed",
                              "Не удалось сохранить локальные ИК-коды")


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/profile_add",
    vol.Required("name"): str,
    vol.Required("entity_id"): str,
    vol.Optional("use_preset", default=False): bool,
    vol.Optional("template_id"): str,
    vol.Optional("profile_type"): str,
    vol.Optional("icon"): str,
    vol.Optional("language", default="en"): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_profile_add(hass, connection, msg):
    runtime = _rt(hass)
    try:
        name = clean_label(msg["name"], limit=64)
        entity_id = remote_entity_id(msg["entity_id"])
        state = hass.states.get(entity_id)
        if state is None:
            raise ValueError("Сущность не найдена в Home Assistant")
        if getattr(state, "attributes", {}).get("ir_studio_virtual"):
            raise ValueError("Выбери физический ИК-шлюз, а не виртуальный пульт IR Studio")
        if len(runtime.profiles) >= 24:
            raise ValueError("Максимум 24 профиля")
        if any(p["name"].casefold() == name.casefold() for p in runtime.profiles):
            raise ValueError("Профиль с таким названием уже есть")
        template_id = msg.get("template_id")
        profile_type = msg.get("profile_type") or template_id or ""
        icon = validate_icon_id(runtime.icons, msg.get("icon") or
                                (profile_type if profile_type in {i["id"] for i in runtime.icons}
                                 else "blank_remote"))
        valid_types = {item["id"] for cat in runtime.template_catalog.get("categories", [])
                       for item in cat.get("templates", [])}
        if profile_type and profile_type not in valid_types:
            raise ValueError("Неизвестный тип устройства")
        if template_id:
            # The template is only a creation-time scaffold. Its ID/type is not
            # persisted in the profile and never changes command execution.
            buttons = build_template_buttons(runtime.template_catalog, template_id, msg.get("language", "en"))
        else:
            preset = runtime.presets.get(name, []) if msg["use_preset"] else []
            buttons = [
                {"id": uuid.uuid4().hex, "name": item, "remote_name": item,
                 "status": "pending", "verified": False}
                for item in preset
            ]
        profile = {
            "id": uuid.uuid4().hex, "name": name, "remote_device": name, "remote_entity": entity_id,
            "buttons": buttons,
            "template_id": template_id or "",
            "profile_type": profile_type,
            "icon": icon,
            "button_origin": "user_selected_template" if template_id else "manual",
        }
        for item in profile["buttons"]:
            if _known_code(hass, profile, item):
                item["status"] = "stored"
        async with runtime.lock:
            runtime.profiles.append(profile)
            await runtime.save()
        connection.send_result(msg["id"], {"id": profile["id"], "buttons": len(buttons)})
    except ValueError as exc:
        _fail(connection, msg, exc)


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/profile_set_icon",
    vol.Required("profile_id"): str,
    vol.Required("icon"): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_profile_set_icon(hass, connection, msg):
    """Update the visual glyph only. CodeStores and Remote keys stay unchanged."""
    runtime = _rt(hass)
    try:
        icon = validate_icon_id(runtime.icons, msg["icon"])
        async with runtime.lock:
            profile = runtime.find_profile(msg["profile_id"])
            previous = profile.get("icon")
            previous_mdi = profile.pop("icon_mdi", None)
            profile["icon"] = icon
            try:
                await runtime.save()
            except Exception:
                if previous is None:
                    profile.pop("icon", None)
                else:
                    profile["icon"] = previous
                if previous_mdi is not None:
                    profile["icon_mdi"] = previous_mdi
                raise
        connection.send_result(msg["id"], {"icon": icon, "buttons_added": 0})
    except ValueError as exc:
        _fail(connection, msg, exc)


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/profile_set_type",
    vol.Required("profile_id"): str,
    vol.Required("profile_type"): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_profile_set_type(hass, connection, msg):
    """Change the visual device type without inventing any IR commands."""
    runtime = _rt(hass)
    try:
        kind = msg["profile_type"]
        valid = {item["id"] for cat in runtime.template_catalog.get("categories", [])
                 for item in cat.get("templates", [])}
        if kind not in valid:
            raise ValueError("Неизвестный тип устройства")
        async with runtime.lock:
            profile = runtime.find_profile(msg["profile_id"])
            previous = profile.get("profile_type")
            profile["profile_type"] = kind
            try:
                await runtime.save()
            except Exception:
                if previous is None:
                    profile.pop("profile_type", None)
                else:
                    profile["profile_type"] = previous
                raise
        connection.send_result(msg["id"], {"profile_type": kind, "buttons_added": 0})
    except ValueError as exc:
        _fail(connection, msg, exc)



@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/profile_apply_template",
    vol.Required("profile_id"): str,
    vol.Required("template_id"): str,
    vol.Optional("language", default="ru"): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_profile_apply_template(hass, connection, msg):
    """Add missing preset buttons without overwriting existing learned codes.

    Does not modify remote_device (IR code namespace), button identifiers, the
    selected remote entity, or any saved code. Safe on existing 0/0 accounts.
    """
    runtime = _rt(hass)
    try:
        language = msg.get("language") if msg.get("language") in ("ru", "en") else "ru"
        template_id = msg["template_id"]
        candidates = build_template_buttons(runtime.template_catalog, template_id, language)
        async with runtime.lock:
            profile = runtime.find_profile(msg["profile_id"])
            existing = {
                button.get("remote_name", button["name"]).casefold()
                for button in profile["buttons"]
            }
            added_buttons = []
            for button in candidates:
                key = button["remote_name"].casefold()
                if key not in existing:
                    added_buttons.append(button)
                    existing.add(key)
            if len(profile["buttons"]) + len(added_buttons) > 200:
                raise ValueError("На одном пульте допускается не более 200 кнопок")
            old_template = profile.get("template_id")
            profile["template_id"] = template_id
            profile["buttons"].extend(added_buttons)
            try:
                await runtime.save()
            except Exception:
                if added_buttons:
                    del profile["buttons"][-len(added_buttons):]
                if old_template is None:
                    profile.pop("template_id", None)
                else:
                    profile["template_id"] = old_template
                raise
        connection.send_result(msg["id"], {
            "added": len(added_buttons), "total": len(profile["buttons"]),
            "template_id": template_id,
        })
    except ValueError as exc:
        _fail(connection, msg, exc)
    except Exception as exc:
        _LOGGER.warning("IR Studio template enrichment failed (%s)", type(exc).__name__)
        connection.send_error(msg["id"], "save_failed", "Не удалось сохранить кнопки")



@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/profile_rename",
    vol.Required("profile_id"): str,
    vol.Required("name"): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_profile_rename(hass, connection, msg):
    runtime = _rt(hass)
    try:
        name = clean_label(msg["name"], limit=64)
        async with runtime.lock:
            profile = runtime.find_profile(msg["profile_id"])
            if any(p["id"] != profile["id"] and p["name"].casefold() == name.casefold()
                   for p in runtime.profiles):
                raise ValueError("Пульт с таким названием уже существует")
            # Preserve the original remote namespace so existing learned codes remain addressable.
            profile.setdefault("remote_device", profile["name"])
            profile["name"] = name
            await runtime.save()
        connection.send_result(msg["id"], {"ok": True})
    except ValueError as exc:
        _fail(connection, msg, exc)


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/profile_bind",
    vol.Required("profile_id"): str,
    vol.Required("entity_id"): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_profile_bind(hass, connection, msg):
    runtime = _rt(hass)
    try:
        entity_id = remote_entity_id(msg["entity_id"])
        state = hass.states.get(entity_id)
        if state is None:
            raise ValueError("Сущность не найдена")
        if getattr(state, "attributes", {}).get("ir_studio_virtual"):
            raise ValueError("Виртуальный пульт не может использоваться как ИК-передатчик")
        async with runtime.lock:
            profile = runtime.find_profile(msg["profile_id"])
            profile["remote_entity"] = entity_id
            # Existing codes belong to their old driver: never claim persistence across bindings.
            for button in profile["buttons"]:
                if button["status"] != "pending":
                    button["status"] = "needs_check"
                    button["verified"] = False
            await runtime.save()
        connection.send_result(msg["id"], {"ok": True})
    except ValueError as exc:
        _fail(connection, msg, exc)


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/profile_reorder",
    vol.Required("profile_id"): str,
    vol.Required("target_profile_id"): str,
    vol.Required("position"): vol.In(("before", "after")),
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_profile_reorder(hass, connection, msg):
    """Persist the sidebar order, without changing any HA/IR identity or code."""
    runtime = _rt(hass)
    try:
        async with runtime.lock:
            original = list(runtime.profiles)
            profile_id = msg["profile_id"]
            target_id = msg["target_profile_id"]
            if (not any(p["id"] == profile_id for p in original) or
                    not any(p["id"] == target_id for p in original)):
                raise ValueError("Пульт не найден: обнови список")
            if profile_id == target_id:
                connection.send_result(msg["id"], {"moved": False})
                return
            reorder_buttons(runtime.profiles, profile_id, target_id, msg["position"])
            moved = [p["id"] for p in original] != [
                p["id"] for p in runtime.profiles
            ]
            if moved:
                try:
                    await runtime.save()
                except Exception:
                    runtime.profiles[:] = original
                    raise
        connection.send_result(msg["id"], {"moved": moved})
    except ValueError as exc:
        _fail(connection, msg, exc)
    except Exception as exc:
        _LOGGER.error("IR profile reordering failed (%s)", type(exc).__name__)
        connection.send_error(
            msg["id"], "save_failed",
            "Не удалось сохранить порядок пультов; предыдущий порядок восстановлен",
        )


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/profile_delete",
    vol.Required("profile_id"): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_profile_delete(hass, connection, msg):
    runtime = _rt(hass)
    try:
        async with runtime.lock:
            profile = runtime.find_profile(msg["profile_id"])
            if any(job["status"] == "running" and job["profile_id"] == profile["id"]
                   for job in runtime.jobs.values()):
                raise ValueError("Дождись завершения текущей операции перед удалением профиля")
            runtime.profiles.remove(profile)
            _remove_profile_payloads(runtime, profile["id"])
            await runtime.save()
        # The underlying remote CodeStore is deliberately NOT deleted.
        connection.send_result(msg["id"], {"removed_metadata_only": True})
    except ValueError as exc:
        _fail(connection, msg, exc)


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/button_add",
    vol.Required("profile_id"): str,
    vol.Required("name"): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_button_add(hass, connection, msg):
    runtime = _rt(hass)
    try:
        name = clean_label(msg["name"])
        async with runtime.lock:
            profile = runtime.find_profile(msg["profile_id"])
            if len(profile["buttons"]) >= 200:
                raise ValueError("Максимум 200 команд на профиль")
            if any(btn["name"].casefold() == name.casefold() for btn in profile["buttons"]):
                raise ValueError("Команда уже существует")
            button = {"id": uuid.uuid4().hex, "name": name, "remote_name": name, "status": "pending", "verified": False}
            profile["buttons"].append(button)
            await runtime.save()
        connection.send_result(msg["id"], {"id": button["id"]})
    except ValueError as exc:
        _fail(connection, msg, exc)


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/button_rename",
    vol.Required("profile_id"): str,
    vol.Required("button_id"): str,
    vol.Required("name"): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_button_rename(hass, connection, msg):
    runtime = _rt(hass)
    try:
        name = clean_label(msg["name"])
        async with runtime.lock:
            profile = runtime.find_profile(msg["profile_id"])
            button = runtime.find_button(profile, msg["button_id"])
            if any(b["id"] != button["id"] and b["name"].casefold() == name.casefold()
                   for b in profile["buttons"]):
                raise ValueError("Кнопка с таким названием уже существует")
            # remote_name remains the key used by the underlying Remote integration.
            button.setdefault("remote_name", button["name"])
            button["name"] = name
            await runtime.save()
        connection.send_result(msg["id"], {"ok": True})
    except ValueError as exc:
        _fail(connection, msg, exc)


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/button_move",
    vol.Required("profile_id"): str,
    vol.Required("button_id"): str,
    vol.Required("direction"): vol.In(("up", "down")),
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_button_move(hass, connection, msg):
    runtime = _rt(hass)
    try:
        async with runtime.lock:
            profile = runtime.find_profile(msg["profile_id"])
            buttons = profile["buttons"]
            index = next(i for i, b in enumerate(buttons) if b["id"] == msg["button_id"])
            target = index - 1 if msg["direction"] == "up" else index + 1
            if target < 0 or target >= len(buttons):
                connection.send_result(msg["id"], {"moved": False})
                return
            buttons[index], buttons[target] = buttons[target], buttons[index]
            await runtime.save()
        connection.send_result(msg["id"], {"moved": True})
    except (ValueError, StopIteration) as exc:
        _fail(connection, msg, ValueError("Команда не найдена"))


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/button_reorder",
    vol.Required("profile_id"): str,
    vol.Required("button_id"): str,
    vol.Required("target_button_id"): str,
    vol.Required("position"): vol.In(("before", "after")),
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_button_reorder(hass, connection, msg):
    """Persist drag-and-drop order while retaining stable button IDs and Remote keys."""
    runtime = _rt(hass)
    try:
        async with runtime.lock:
            profile = runtime.find_profile(msg["profile_id"])
            changed = reorder_buttons(
                profile["buttons"],
                msg["button_id"],
                msg["target_button_id"],
                msg["position"],
            )
            if changed:
                await runtime.save()
        connection.send_result(msg["id"], {"moved": changed})
    except ValueError as exc:
        _fail(connection, msg, exc)



@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/button_delete",
    vol.Required("profile_id"): str,
    vol.Required("button_id"): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_button_delete(hass, connection, msg):
    runtime = _rt(hass)
    try:
        async with runtime.lock:
            profile = runtime.find_profile(msg["profile_id"])
            button = runtime.find_button(profile, msg["button_id"])
            profile["buttons"].remove(button)
            _remove_button_payloads(runtime, profile["id"], button["id"])
            await runtime.save()
        connection.send_result(msg["id"], {"removed_metadata_only": True, "studio_payloads_removed": True})
    except ValueError as exc:
        _fail(connection, msg, exc)


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/profile_remove_unlearned",
    vol.Required("profile_id"): str,
    vol.Required("button_ids"): [str],
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_profile_remove_unlearned(hass, connection, msg):
    """Remove explicitly selected, *provably code-free* legacy placeholders.

    Non-empty or unknown remote stores are treated as protected; a UI label
    alone is never evidence that a command has no saved IR waveform.
    """
    runtime = _rt(hass)
    try:
        button_ids = msg["button_ids"]
        if not 1 <= len(button_ids) <= 200 or len(button_ids) != len(set(button_ids)):
            raise ValueError("Выбери от 1 до 200 разных кнопок")
        async with runtime.lock:
            profile = runtime.find_profile(msg["profile_id"])
            # Opt-in cleanup applies to every user profile. Safety is
            # decided by verified state and actual code stores, never name.
            if any(j["status"] in ("running", "cancelling")
                   and j["profile_id"] == profile["id"]
                   for j in runtime.jobs.values()):
                raise ValueError("Дождись завершения обучения")
            by_id = {item["id"]: item for item in profile["buttons"]}
            if any(button_id not in by_id for button_id in button_ids):
                raise ValueError("Список кнопок изменился: обнови пульт")
            for button_id in button_ids:
                button = by_id[button_id]
                if button.get("status") != "pending" or button.get("verified"):
                    raise ValueError("Нельзя удалять обученные или непроверенные команды")
                key = f"{profile['id']}/{button_id}"
                if key in runtime.ir_codes or key in runtime.native_codes:
                    raise ValueError("Для одной из кнопок есть сохранённый ИК-код")
                if _known_code(hass, profile, button) is not False:
                    raise ValueError("Нельзя подтвердить отсутствие ИК-кода у драйвера")
            original = profile["buttons"]
            profile["buttons"] = [
                button for button in original if button["id"] not in button_ids
            ]
            try:
                await runtime.save()
            except Exception:
                profile["buttons"] = original
                raise
        connection.send_result(msg["id"], {
            "removed": len(button_ids), "remaining": len(profile["buttons"]),
            "codes_removed": 0,
        })
    except ValueError as exc:
        _fail(connection, msg, exc)
    except Exception as exc:
        _LOGGER.warning("Placeholder cleanup failed (%s)", type(exc).__name__)
        connection.send_error(msg["id"], "save_failed", "Не удалось очистить профиль")


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/button_add_set",
    vol.Required("profile_id"): str,
    vol.Optional("set_ids", default=[]): [str],
    vol.Optional("command_ids", default=[]): [str],
    vol.Optional("language", default="en"): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_button_add_set(hass, connection, msg):
    """Append selected command-library sets without overwriting existing buttons."""
    runtime = _rt(hass)
    try:
        async with runtime.lock:
            profile = runtime.find_profile(msg["profile_id"])
            set_ids = msg.get("set_ids", [])
            command_ids = msg.get("command_ids", [])
            if not set_ids and not command_ids:
                raise ValueError("Выбери наборы или отдельные команды")
            candidates = []
            if set_ids:
                candidates.extend(build_button_set(runtime.template_catalog, set_ids, msg.get("language", "en")))
            if command_ids:
                candidates.extend(build_command_buttons(runtime.template_catalog, command_ids, msg.get("language", "en")))
            existing = {button.get("remote_name", button["name"]).casefold() for button in profile["buttons"]}
            added_buttons = []
            skipped = 0
            candidate_keys = set()
            for button in candidates:
                key = button["remote_name"].casefold()
                if key in candidate_keys:
                    skipped += 1
                    continue
                candidate_keys.add(key)
                if key in existing:
                    skipped += 1
                    continue
                existing.add(key)
                added_buttons.append(button)
            if len(profile["buttons"]) + len(added_buttons) > 200:
                raise ValueError("Достигнут лимит 200 команд на пульт")
            profile["buttons"].extend(added_buttons)
            added = len(added_buttons)
            if added:
                await runtime.save()
        connection.send_result(msg["id"], {"added": added, "skipped": skipped})
    except ValueError as exc:
        _fail(connection, msg, exc)


async def _run_service(hass, runtime, job_id, *, user_id: str):
    job = runtime.jobs[job_id]
    profile = runtime.find_profile(job["profile_id"])
    button = runtime.find_button(profile, job["button_id"])
    entity = profile["remote_entity"]
    if job["kind"] == "learn":
        domain, service = "remote", "learn_command"
        data = {
            "entity_id": entity,
            "device": profile.get("remote_device", profile["name"]),
            "command": [button.get("remote_name", button["name"])],
            "command_type": "ir",
            "timeout": job["timeout"],
        }
        timeout = job["timeout"] + 20
    else:
        domain, service = "remote", "send_command"
        data = {"entity_id": entity, "device": profile.get("remote_device", profile["name"]), "command": [button.get("remote_name", button["name"])]}
        timeout = 30
    try:
        # Some integrations use remote.turn_on only as a local guard. If the
        # remote is off, enable it before learning/sending; it is NOT an IR
        # command and does not turn on a TV.
        remote_state = hass.states.get(entity)
        entity_source = _source(hass, entity)
        # Tuya Local remote.off is its normal idle state; it does not need a
        # remote.turn_on guard before learning or sending.
        if (
            remote_state is not None
            and remote_state.state == "off"
            and entity_source != "tuya_local"
        ):
            await hass.services.async_call(
                "remote", "turn_on", {"entity_id": entity},
                blocking=True, context=Context(user_id=user_id),
            )
        await asyncio.wait_for(
            hass.services.async_call(
                domain, service, data, blocking=True,
                context=Context(user_id=user_id),
            ),
            timeout=timeout,
        )
        if job["kind"] == "learn":
            if entity_source == "tuya_local":
                # Tuya Local returns from learn_command only after DP202 has
                # been received and its own Store.async_save has completed.
                button["status"] = "stored"
                job["message"] = (
                    "Tuya Local сохранила DP202-код в собственном хранилище. "
                    "Следующий шаг — отправить его и проверить физическую реакцию."
                )
            else:
                code_is_stored = _known_code(hass, profile, button)
                button["status"] = "stored" if code_is_stored else "needs_check"
                job["message"] = (
                    "Код найден в локальном хранилище tuya_ir. Следующий шаг — отправить его и проверить физически."
                    if code_is_stored else
                    "HA завершил обучение без ошибки, но наличие raw-кода в хранилище не подтверждено. Попробуй отправку или проверь журнал интеграции."
                )
            button["verified"] = False
            job["status"] = "done"
        else:
            job["status"] = "done"
            job["message"] = "Вызов отправки завершился без ошибки. Подтверди, отреагировало ли устройство физически."
        await runtime.save()
    except asyncio.CancelledError:
        job["status"] = "cancelled"
        job["message"] = "Операция отменена"
        raise
    except Exception as exc:  # remote platform exceptions differ by backend
        job["status"] = "failed"
        # Do not expose TinyTuya/network exception text, which may contain
        # addresses, protocol details or device-specific payload fragments.
        job["message"] = "Операция не выполнена. Проверь журнал Home Assistant."
        _LOGGER.warning("IR Studio remote.%s failed: %s", job["kind"], type(exc).__name__)
    finally:
        job["finished_at"] = time.time()
        runtime.job_tasks.pop(job_id, None)


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/start",
    vol.Required("kind"): vol.In(("learn", "send")),
    vol.Required("profile_id"): str,
    vol.Required("button_id"): str,
    vol.Optional("timeout", default=60): vol.All(vol.Coerce(int), vol.Range(min=10, max=90)),
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_start(hass, connection, msg):
    runtime = _rt(hass)
    try:
        p = runtime.find_profile(msg["profile_id"])
        runtime.find_button(p, msg["button_id"])
        state = hass.states.get(p["remote_entity"])
        if state is None:
            raise ValueError("Remote-сущность больше не существует")
        if state.state in ("unavailable", "unknown"):
            raise ValueError("Remote сейчас unavailable. Сначала восстанови LAN-подключение к ИК-хабу")
        if msg["kind"] == "send":
            btn = runtime.find_button(p, msg["button_id"])
            if btn["status"] == "pending" and not _known_code(hass, p, btn):
                raise ValueError("Пока нет подтверждения сохранённого ИК-кода. Сначала обучи кнопку")
        job_id = runtime.new_job(msg["kind"], p["id"], msg["button_id"])
        runtime.jobs[job_id]["timeout"] = msg["timeout"]
        task = hass.async_create_task(_run_service(hass, runtime, job_id, user_id=connection.user.id))
        runtime.job_tasks[job_id] = task
        connection.send_result(msg["id"], {"job_id": job_id})
    except ValueError as exc:
        _fail(connection, msg, exc)


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/job",
    vol.Required("job_id"): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_job(hass, connection, msg):
    job = _rt(hass).jobs.get(msg["job_id"])
    if not job:
        return connection.send_error(msg["id"], "not_found", "Операция не найдена")
    connection.send_result(msg["id"], dict(job))


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/job_cancel",
    vol.Required("job_id"): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_job_cancel(hass, connection, msg):
    """Request cancellation; actual idle state follows service cleanup."""
    runtime = _rt(hass)
    job = runtime.jobs.get(msg["job_id"])
    if job is None:
        connection.send_error(msg["id"], "not_found", "Операция не найдена")
        return
    if job["kind"] != "learn":
        connection.send_error(msg["id"], "invalid_request", "Отмена доступна для обучения")
        return
    task = runtime.job_tasks.get(msg["job_id"])
    if job["status"] in ("running", "cancelling") and task is not None and not task.done():
        job["status"] = "cancelling"
        job["message"] = "Останавливаем приём ИК-сигнала…"
        task.cancel()
    connection.send_result(msg["id"], {"status": job["status"]})


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/verify",
    vol.Required("job_id"): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_verify(hass, connection, msg):
    runtime = _rt(hass)
    job = runtime.jobs.get(msg["job_id"])
    if not job or job["kind"] != "send" or job["status"] != "done":
        return connection.send_error(msg["id"], "invalid_request", "Нужна успешно завершённая отправка")
    try:
        profile = runtime.find_profile(job["profile_id"])
        button = runtime.find_button(profile, job["button_id"])
        button["verified"] = True
        button["status"] = "verified"
        button["verified_at"] = time.time()
        await runtime.save()
        connection.send_result(msg["id"], {"verified": True})
    except ValueError as exc:
        _fail(connection, msg, exc)


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/import_raw",
    vol.Required("profile_id"): str,
    vol.Required("button_id"): str,
    vol.Optional("base64"): str,  # Legacy field name retained for existing clients.
    vol.Optional("payload"): str,
    vol.Optional("format", default="raw_ir"): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_import_raw(hass, connection, msg):
    """Store a typed IR payload without converting between driver formats."""
    runtime = _rt(hass)
    try:
        payload = msg.get("payload", msg.get("base64"))
        if not isinstance(payload, str) or not payload.strip():
            raise ValueError("Вставь ИК-код для импорта")
        payload_format = msg.get("format", "raw_ir")
        if payload_format not in ("raw_ir", "tuya_dp202"):
            raise ValueError("Неподдерживаемый формат ИК-кода")

        async with runtime.lock:
            profile = runtime.find_profile(msg["profile_id"])
            button = runtime.find_button(profile, msg["button_id"])
            ent = er.async_get(hass).async_get(profile["remote_entity"])

            if payload_format == "tuya_dp202":
                code = validate_code(payload)
                if not ent or ent.platform != DOMAIN or profile["remote_entity"] not in runtime.native_remotes:
                    raise ValueError("Импорт Tuya DP202 требует нативный Remote ИК Студии")
                runtime.native_codes[f"{profile['id']}/{button['id']}"] = code
            else:
                code = validate_raw_b64(payload)
                if not ent or ent.platform != "tuya_ir" or not ent.config_entry_id:
                    raise ValueError("Импорт RAW Base64 требует локальный tuya_ir Remote")
                target = hass.data.get("tuya_ir", {}).get(ent.config_entry_id)
                if not target or not hasattr(target, "store"):
                    raise ValueError("Локальное хранилище tuya_ir не найдено")
                await target.store.async_set(
                    profile.get("remote_device", profile["name"]),
                    button.get("remote_name", button["name"]),
                    code,
                )

            button["status"] = "stored"
            button["verified"] = False
            await runtime.save()

        connection.send_result(msg["id"], {"stored": True, "format": payload_format, "needs_physical_test": True})
    except ValueError as exc:
        _fail(connection, msg, exc)
    except Exception as exc:
        _LOGGER.warning("IR Studio code import failed: %s", type(exc).__name__)
        _fail(connection, msg, ValueError("Не удалось сохранить ИК-код"))



def _read_export_code(hass, runtime, profile, button):
    """Read only portable IR waveforms, never credentials or private metadata."""
    key = f"{profile['id']}/{button['id']}"
    code = runtime.native_codes.get(key)
    if code:
        return {"format": "tuya_dp202", "code": code}
    code = runtime.ir_codes.get(key)
    if code:
        return code
    native = runtime.native_remotes.get(profile["remote_entity"])
    if native:
        raw = native.get_code(profile.get("remote_device", profile["name"]),
                              button.get("remote_name", button["name"]))
        if raw:
            return {"format": "tuya_dp202", "code": raw}
    entry = er.async_get(hass).async_get(profile["remote_entity"])
    if not entry or entry.platform != "tuya_ir" or not entry.config_entry_id:
        return None
    driver = hass.data.get("tuya_ir", {}).get(entry.config_entry_id)
    if driver is None or not hasattr(driver, "store"):
        return None
    try:
        return driver.store.get(profile.get("remote_device", profile["name"]),
                                button.get("remote_name", button["name"]))
    except Exception as exc:
        # A backend can be unavailable or have an incompatible CodeStore API.
        _LOGGER.debug("RAW export unavailable: %s", type(exc).__name__)
        return None


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/backup_export",
    vol.Required("profile_ids"): [str],
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_backup_export(hass, connection, msg):
    runtime = _rt(hass)
    try:
        profile_ids = msg["profile_ids"]
        if not profile_ids or len(set(profile_ids)) != len(profile_ids) or len(profile_ids) > 24:
            raise ValueError("Выбери пульты для экспорта")
        async with runtime.lock:
            profiles = []
            raw_count = 0
            for pid in profile_ids:
                profile = runtime.find_profile(pid)
                data, amount = strip_export_profile(profile, lambda p, b: _read_export_code(hass, runtime, p, b))
                profiles.append(data)
                raw_count += amount
        count = sum(len(p["buttons"]) for p in profiles)
        connection.send_result(msg["id"], {
            "format": FORMAT, "format_version": 3, "exported_at": datetime.now(timezone.utc).isoformat(),
            "profiles": profiles,
            "raw_ir_codes_included": raw_count,
            "raw_ir_codes_unavailable": count - raw_count,
            "note": "IR waveforms are included only when readable from a supported local code store.",
        })
    except ValueError as exc:
        _fail(connection, msg, exc)


@websocket_api.websocket_command({
    vol.Required("type"): "ir_studio/backup_import",
    vol.Required("backup"): dict,
    vol.Required("profile_ids"): [str],
    vol.Required("strategy"): vol.In(("skip", "merge", "replace")),
    vol.Optional("dry_run", default=True): bool,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_backup_import(hass, connection, msg):
    runtime = _rt(hass)
    try:
        async with runtime.lock:
            incoming = normalize_backup(msg["backup"], valid_icons=runtime.icons)
            selected_incoming = [
                profile for profile in incoming if profile["id"] in msg["profile_ids"]
            ]
            replaced_profile_ids = set()
            if msg["strategy"] == "replace":
                for incoming_profile in selected_incoming:
                    existing = next(
                        (
                            profile for profile in runtime.profiles
                            if profile["id"] == incoming_profile["id"]
                            or profile["name"].casefold() == incoming_profile["name"].casefold()
                        ),
                        None,
                    )
                    if existing is not None:
                        replaced_profile_ids.add(existing["id"])

            target, changes = make_import_plan(
                runtime.profiles, msg["backup"], msg["profile_ids"], msg["strategy"],
                valid_icons=runtime.icons,
            )
            if not msg["dry_run"]:
                # Replacement removes only IR Studio-owned payloads for the old
                # profile. External driver CodeStores are deliberately untouched.
                new_codes = dict(runtime.ir_codes)
                new_native_codes = dict(runtime.native_codes)
                for profile_id in replaced_profile_ids:
                    prefix = f"{profile_id}/"
                    new_codes = {
                        key: value for key, value in new_codes.items()
                        if not key.startswith(prefix)
                    }
                    new_native_codes = {
                        key: value for key, value in new_native_codes.items()
                        if not key.startswith(prefix)
                    }
                # Raw IR stays in OUR separate code store, not an unrelated backend.
                # Its presence does not imply the physical remote has learned it.
                for profile in target:
                    for button in profile["buttons"]:
                        code = button.pop("raw_ir", None)
                        if code is not None:
                            key = f"{profile['id']}/{button['id']}"
                            if msg["strategy"] == "replace" or key not in new_codes:
                                new_codes[key] = code
                        native_code = button.pop("tuya_code", None)
                        if native_code is not None:
                            key = f"{profile['id']}/{button['id']}"
                            if msg["strategy"] == "replace" or key not in new_native_codes:
                                new_native_codes[key] = native_code
                        # Never flag imported waveforms as physically verified.
                # Keep original backups in their own Store; never delete old waveform entries.
                runtime.profiles = target
                runtime.ir_codes = new_codes
                runtime.native_codes = new_native_codes
                await runtime.save()
        connection.send_result(msg["id"], {
            "ok": True, "dry_run": msg["dry_run"], "changes": changes,
            "note": "Imported code payloads are stored in IR Studio. Tuya DP202 codes can be sent via a bound native IR Studio remote; other driver formats are not converted automatically."
        })
    except ValueError as exc:
        _fail(connection, msg, exc)

def register_commands(hass):
    for command in (
        ws_get, ws_ir_file_preview, ws_ir_file_import, ws_profile_add, ws_profile_set_icon, ws_profile_set_type, ws_profile_apply_template, ws_profile_rename, ws_profile_bind, ws_profile_delete, ws_profile_reorder,
        ws_button_add, ws_button_add_set, ws_button_rename, ws_button_move, ws_button_reorder, ws_button_delete, ws_profile_remove_unlearned, ws_start, ws_job, ws_verify, ws_import_raw,
        ws_backup_export, ws_backup_import, ws_job_cancel,
    ):
        websocket_api.async_register_command(hass, command)
