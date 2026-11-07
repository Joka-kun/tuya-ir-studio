"""Proof that imported IR buttons get real u16LE pulse payloads, never labels."""
import base64
import importlib.util
from pathlib import Path
import struct

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "ir_studio" / "ir_file_import.py"
spec = importlib.util.spec_from_file_location("ir_file_parser_under_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


FIXTURE = """Filetype: IR signals file
Version: 1
#
name: Volume+
type: raw
frequency: 38000
duty_cycle: 0.330000
data: 9000 4500 563 563 563 1688 563 30000
#
name: PowerOn
type: parsed
protocol: NEC
address: 04 00 00 00
command: 5E 00 00 00
#
name: PowerOff
type: parsed
protocol: NECext
address: EE 87 00 00
command: 5D 00 00 00
#
name: Menu
type: parsed
protocol: Samsung32
address: 07 00 00 00
command: 10 00 00 00
"""


def samples(code):
    raw = base64.b64decode(code, validate=True)
    return list(struct.unpack("<" + "H" * (len(raw) // 2), raw))


def test_valid_raw_and_parsed_nec_create_actual_timings_not_command_names():
    result = module.parse_flipper_ir(FIXTURE)
    assert result["total"] == 4
    assert result["supported_names"] == ["Volume+", "PowerOn", "PowerOff"]
    assert result["unsupported"] == [{"name": "Menu", "reason": "protocol_unsupported"}]
    assert samples(result["codes"]["Volume+"]) == [
        9000, 4500, 563, 563, 563, 1688, 563, 30000,
    ]
    for key in ("PowerOn", "PowerOff"):
        timings = samples(result["codes"][key])
        assert len(timings) == 68
        assert timings[:2] == [9000, 4500]
        assert timings[-2:] == [563, 30000]
        assert set(timings).issubset({9000, 4500, 563, 1688, 30000})
    # Different address/code means different physical IR signals.
    assert result["codes"]["PowerOn"] != result["codes"]["PowerOff"]


def test_nec_address_and_command_bit_encoding_independent_reference():
    # NEC 0x00 -> complement 0xFF, command 0x00 -> complement 0xFF.
    zero = module._nec_pulses(0, 0, extended=False)
    assert zero[:2] == [9000, 4500]
    assert zero[2:18] == [563, 563] * 8  # all zero data bits
    assert zero[18:34] == [563, 1688] * 8  # inverse address
    assert zero[34:50] == [563, 563] * 8  # command zero
    assert zero[50:66] == [563, 1688] * 8  # inverse command


def test_tcl_irdb_necext_preserves_both_address_and_command_bytes():
    # Published TCL_32S327.ir has address EA C7, command 17 E8, both 16-bit.
    # Decode pulse widths independently in LSB-first order.
    pulses = module._nec_pulses(0xC7EA, 0xE817, extended=True)
    bits = [1 if pulses[3 + 2 * i] == 1688 else 0 for i in range(32)]
    actual = [
        sum(bits[8 * j + bit] << bit for bit in range(8))
        for j in range(4)
    ]
    assert actual == [0xEA, 0xC7, 0x17, 0xE8]
    # NECext command does not necessarily contain an inverse pair.
    other = module._nec_pulses(0x87EE, 0xA05D, extended=True)
    other_bits = [1 if other[3 + 2 * i] == 1688 else 0 for i in range(32)]
    assert [sum(other_bits[8*j+b] << b for b in range(8))
            for j in range(4)] == [0xEE, 0x87, 0x5D, 0xA0]


@pytest.mark.parametrize("mutation", [
    lambda x: x.replace("Filetype: IR signals file", "Filetype: arbitrary"),
    lambda x: x.replace("Version: 1", "Version: 2"),
    lambda x: x.replace("9000 4500", "0 4500"),
    lambda x: x.replace("9000 4500", "65536 4500"),
    lambda x: x.replace("04 00 00 00", "ZZ 00 00 00"),
    lambda x: x.replace("name: Volume+", "name: PowerOn"),
])
def test_bad_file_or_fabricated_raw_values_rejected(mutation):
    with pytest.raises(ValueError):
        module.parse_flipper_ir(mutation(FIXTURE))


def test_wrong_carrier_never_claimed_as_sendable():
    result = module.parse_flipper_ir(FIXTURE.replace("frequency: 38000", "frequency: 36000"))
    assert "Volume+" not in result["codes"]
    assert {"name": "Volume+", "reason": "carrier_not_38khz"} in result["unsupported"]


def test_library_metadata_only_has_zero_codes():
    data = """Filetype: IR signals file
Version: 1
#
name: PowerOn
type: parsed
protocol: RC5
address: 01 00 00 00
command: 01 00 00 00
"""
    result = module.parse_flipper_ir(data)
    assert result["codes"] == {}
    assert result["supported_names"] == []
    assert result["total"] == 1
