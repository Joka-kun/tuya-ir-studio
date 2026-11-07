import base64
import importlib.util
import json
from pathlib import Path
import struct

import pytest

HERE = Path(__file__).resolve().parents[1] / 'custom_components' / 'ir_studio'
spec = importlib.util.spec_from_file_location('ir_studio_utils_for_test', HERE / 'utils.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_presets_are_a_generic_bilingual_device_template_catalog():
    data = json.loads((HERE / 'presets.json').read_text(encoding='utf-8'))
    assert data['schema_version'] == 2
    assert len(data['categories']) >= 12
    template_ids = [item['id'] for category in data['categories'] for item in category['templates']]
    assert 'projector' in template_ids  # generic projector is not a personal device profile
    assert all('TCL' not in item['labels'].values() and 'Hisense' not in item['labels'].values()
               for category in data['categories'] for item in category['templates'])
    for category in data['categories']:
        assert set(category['labels']) == {'en', 'ru'}
        for item in category['templates']:
            assert set(item['labels']) == {'en', 'ru'}
            assert all(command_id in data['commands'] for command_id in item['buttons'])
    # Templates contain command labels and keys only, never learned signals or credentials.
    assert all('raw_ir' not in command and 'tuya_code' not in command and 'local_key' not in command
               for command in data['commands'].values())


def test_valid_raw_u16le_passes():
    code=base64.b64encode(struct.pack('<'+'H'*32, *([9000,4500]+[570,580]*15))).decode()
    assert module.validate_raw_b64(code) == code
    assert module.validate_raw_b64('b64:'+code) == code


@pytest.mark.parametrize('code', ['foo','rawcode', '!!base64', '', 'eA==', base64.b64encode(b'\x00'*30).decode()])
def test_invalid_raw_rejected(code):
    with pytest.raises(ValueError):
        module.validate_raw_b64(code)


@pytest.mark.parametrize('value', ['', ' ', '\n', 'A'*97])
def test_invalid_label(value):
    with pytest.raises(ValueError):
        module.clean_label(value)


def test_remote_id_restricted():
    assert module.remote_entity_id('remote.smart_ir_remote_control')=='remote.smart_ir_remote_control'
    for value in ('light.test','remote.X','remote.test;rm -rf /','remote.a b'):
        with pytest.raises(ValueError):module.remote_entity_id(value)


def test_reorder_buttons_before_and_after_preserves_ids_and_keys():
    buttons = [
        {"id": "a", "name": "Power", "remote_name": "Power"},
        {"id": "b", "name": "Volume+", "remote_name": "Volume+"},
        {"id": "c", "name": "Mute", "remote_name": "Mute"},
    ]
    assert module.reorder_buttons(buttons, "c", "a", "before") is True
    assert [b["id"] for b in buttons] == ["c", "a", "b"]
    assert buttons[0]["remote_name"] == "Mute"
    assert module.reorder_buttons(buttons, "c", "b", "after") is True
    assert [b["id"] for b in buttons] == ["a", "b", "c"]


def test_reorder_buttons_noop_and_invalid_ids():
    buttons = [{"id": "a", "name": "Power", "remote_name": "Power"}]
    assert module.reorder_buttons(buttons, "a", "a", "before") is False
    assert [b["id"] for b in buttons] == ["a"]
    with pytest.raises(ValueError):
        module.reorder_buttons(buttons, "missing", "a", "before")
    with pytest.raises(ValueError):
        module.reorder_buttons(buttons, "a", "missing", "before")
    with pytest.raises(ValueError):
        module.reorder_buttons(buttons, "a", "a", "sideways")


def test_brand_assets_exist_with_home_assistant_sizes():
    import struct
    brand = HERE / "brand"
    for filename, size in [
        ("icon.png", (256, 256)),
        ("icon@2x.png", (512, 512)),
        ("dark_icon.png", (256, 256)),
        ("dark_icon@2x.png", (512, 512)),
    ]:
        data = (brand / filename).read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack(">II", data[16:24]) == size
