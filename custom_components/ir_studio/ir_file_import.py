"""Strict offline Flipper .ir waveform reader for explicitly selected profiles.

Imports only actual raw pulses and the two NEC variants we can encode exactly.
No account metadata / human-readable key name is ever interpreted as waveform.
Unsupported protocols are reported, not fabricated. This module is pure Python.
"""
from __future__ import annotations

import base64
import re
import struct

MAX_FILE_CHARS = 200_000
MAX_BUTTONS = 100
MAX_PULSES = 1024
SUPPORTED_CARRIER = 38_000
DUTY_MIN, DUTY_MAX = 0.31, 0.35


def _reverse8(n: int) -> int:
    return int(f"{n:08b}"[::-1], 2)


def _nec_pulses(address: int, command: int, *, extended: bool) -> list[int]:
    """NEC/NECext address and command are Flipper's little-endian integers."""
    if not 0 <= address <= (0xFFFF if extended else 0xFF):
        raise ValueError("Invalid NEC address")
    if not 0 <= command <= (0xFFFF if extended else 0xFF):
        raise ValueError("Invalid NEC command")
    a0 = _reverse8(address & 0xFF)
    a1 = _reverse8((address >> 8) & 0xFF if extended else (~address) & 0xFF)
    c0 = _reverse8(command & 0xFF)
    # NECext is 16-bit command as well as 16-bit address; its second byte
    # is NOT necessarily the complement (see Flipper official 5D A0 sample).
    c1 = _reverse8((command >> 8) & 0xFF if extended else (~command) & 0xFF)
    frame = (a0 << 24) | (a1 << 16) | (c0 << 8) | c1
    pulses = [9000, 4500]
    for bit in range(31, -1, -1):
        pulses.extend((563, 1688 if frame & (1 << bit) else 563))
    pulses.extend((563, 30000))
    return pulses


def _pulse_code(samples: list[int]) -> str:
    if not 2 <= len(samples) <= MAX_PULSES:
        raise ValueError("Invalid pulse count")
    if any(type(pulse) is not int or not 0 < pulse <= 65535 for pulse in samples):
        raise ValueError("Invalid u16 timing")
    return base64.b64encode(struct.pack("<" + "H" * len(samples), *samples)).decode("ascii")


def _flipper_int(value: str) -> int:
    if not re.fullmatch(r"[0-9]{1,6}", value.strip()):
        raise ValueError("Invalid timing or carrier")
    return int(value.strip())


def _parsed_bytes(value: str) -> int:
    items = value.split()
    if len(items) != 4 or any(not re.fullmatch(r"[a-fA-F0-9]{2}", x) for x in items):
        raise ValueError("Invalid Flipper parsed bytes")
    return int.from_bytes(bytes(int(x, 16) for x in items), "little")


def parse_flipper_ir(source: str) -> dict:
    """Return verified names + Base64 waveforms, and summary of unsupported keys.

    Flipper supports many codecs; never silently approximate them.
    A valid file can contain unsupported parsed protocols alongside supported
    raw/NEC entries. Unsupported records are counted but not importable.
    """
    if not isinstance(source, str) or not 25 <= len(source) <= MAX_FILE_CHARS:
        raise ValueError("Invalid IR file size")
    lines = source.replace("\r\n", "\n").lstrip("\ufeff").split("\n")
    header, entries, current = {}, [], None
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError("Malformed Flipper IR line")
        key, value = [part.strip() for part in line.split(":", 1)]
        if key == "name":
            if current is not None:
                entries.append(current)
            current = {"name": value}
        elif current is None:
            if key in ("Filetype", "Version"):
                header[key] = value
        else:
            if key in current:
                raise ValueError("Duplicate IR field")
            current[key] = value
    if current is not None:
        entries.append(current)
    if header.get("Filetype") not in ("IR signals file", "IR signals library") or header.get("Version") != "1":
        raise ValueError("Unsupported Flipper file header")
    if not 1 <= len(entries) <= MAX_BUTTONS:
        raise ValueError("Invalid number of buttons")
    codes, unsupported, seen = {}, [], set()
    for entry in entries:
        name = entry.get("name", "")
        if not 1 <= len(name) <= 96 or any(not 32 <= ord(c) <= 126 for c in name):
            raise ValueError("Invalid Flipper key name")
        normalized = name.casefold()
        if normalized in seen:
            raise ValueError("Duplicate Flipper command name")
        seen.add(normalized)
        mode = entry.get("type")
        if mode == "raw":
            if _flipper_int(entry.get("frequency", "")) != SUPPORTED_CARRIER:
                unsupported.append({"name": name, "reason": "carrier_not_38khz"})
                continue
            try:
                duty = float(entry.get("duty_cycle", ""))
            except ValueError as exc:
                raise ValueError("Invalid duty cycle") from exc
            if not DUTY_MIN <= duty <= DUTY_MAX:
                unsupported.append({"name": name, "reason": "duty_cycle_unsupported"})
                continue
            raw_data = entry.get("data", "").split()
            if len(raw_data) > MAX_PULSES:
                raise ValueError("IR pulse count too high")
            pulses = [_flipper_int(x) for x in raw_data]
        elif mode == "parsed":
            proto = entry.get("protocol")
            if proto not in ("NEC", "NECext"):
                unsupported.append({"name": name, "reason": "protocol_unsupported"})
                continue
            pulses = _nec_pulses(
                _parsed_bytes(entry.get("address", "")),
                _parsed_bytes(entry.get("command", "")),
                extended=(proto == "NECext"),
            )
        else:
            unsupported.append({"name": name, "reason": "type_unsupported"})
            continue
        codes[name] = _pulse_code(pulses)
    return {
        "codes": codes,
        "supported_names": list(codes),
        "unsupported": unsupported,
        "total": len(entries),
    }
