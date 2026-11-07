"""Pure, separately testable code and label validators."""
from __future__ import annotations

import base64
import binascii
import re
import struct

_ENTITY = re.compile(r"^remote\.[a-z0-9_]+$")


def clean_label(value: str, *, limit: int = 96) -> str:
    """Reject whitespace-only, control characters and overlong button names."""
    if not isinstance(value, str):
        raise ValueError("Название должно быть строкой")
    result = value.strip()
    if not result or len(result) > limit or any(ord(c) < 32 for c in result):
        raise ValueError(f"Название должно содержать 1–{limit} печатных символов")
    return result


def remote_entity_id(value: str) -> str:
    if not isinstance(value, str) or not _ENTITY.fullmatch(value):
        raise ValueError("Выбери HA-сущность remote.*")
    return value


def validate_raw_b64(code: str) -> str:
    """Accept only plausible, uncompressed u16-LE timing sequences for Wi-Fi IR.

    This is format validation, NOT proof that the command will actuate an appliance.
    """
    if not isinstance(code, str):
        raise ValueError("Ожидается строка Base64")
    code = code.strip()
    if code.startswith("b64:"):
        code = code[4:]
    try:
        payload = base64.b64decode(code, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Некорректный Base64") from exc
    if not 24 <= len(payload) <= 8192 or len(payload) % 2:
        raise ValueError("Ожидались 12–4096 значений длительности, по 2 байта")
    pulses = struct.unpack("<" + "H" * (len(payload) // 2), payload)
    if any(pulse < 20 for pulse in pulses):
        raise ValueError("Найдена неправдоподобно короткая длительность импульса")
    if sum(pulses) > 30_000_000:
        raise ValueError("Слишком длинный сигнал")
    return code


def reorder_buttons(buttons: list[dict], button_id: str, target_button_id: str, position: str) -> bool:
    """Move one button before/after another without changing either button's identity."""
    if position not in ("before", "after"):
        raise ValueError("Позиция должна быть before или after")
    source_index = next((i for i, item in enumerate(buttons) if item.get("id") == button_id), None)
    target_index = next((i for i, item in enumerate(buttons) if item.get("id") == target_button_id), None)
    if source_index is None or target_index is None:
        raise ValueError("Команда не найдена")
    if button_id == target_button_id:
        return False
    moving = buttons.pop(source_index)
    target_index = next(i for i, item in enumerate(buttons) if item.get("id") == target_button_id)
    buttons.insert(target_index + (1 if position == "after" else 0), moving)
    return True
