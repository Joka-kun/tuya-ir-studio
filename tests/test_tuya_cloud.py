"""Tests for account-device normalization and gateway mapping."""
import importlib.util
from types import SimpleNamespace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLOUD_PATH = ROOT / "custom_components" / "ir_studio" / "tuya_cloud.py"
SPEC = importlib.util.spec_from_file_location("ir_studio_tuya_cloud", CLOUD_PATH)
CLOUD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLOUD)

normalize_cloud_devices = CLOUD.normalize_cloud_devices
resolve_hub_target = CLOUD.resolve_hub_target


def _device(**kwargs):
    defaults = {
        "id": "parent-id",
        "node_id": "",
        "uuid": "",
        "local_key": "parent-key",
        "category": "zigbee",
        "ip": "",
        "name": "IR gateway",
        "online": True,
        "product_id": "gateway-product",
        "product_name": "IR gateway",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_normalize_cloud_devices_keeps_parent_and_child_distinct():
    devices = normalize_cloud_devices(
        [
            _device(),
            _device(
                node_id="child-node",
                uuid="child-uuid",
                local_key="child-key",
                category="infrared",
                name="IR module",
                product_name="IR module",
            ),
        ]
    )
    assert set(devices) == {"parent-id", "parent-id/child-node"}
    assert devices["parent-id"]["is_hub"] is True
    assert devices["parent-id/child-node"]["is_hub"] is False



def test_yrc11_universal_ir_category_is_classified_as_a_direct_hub():
    devices = normalize_cloud_devices([
        _device(
            category="wnykq",
            ip="192.168.2.110",
            name="YRC11",
            product_name="Universal IR Remote",
        )
    ])
    assert devices["parent-id"]["is_hub"] is True
    target = resolve_hub_target(devices, "parent-id", "parent-id")
    assert target["device_id"] == "parent-id"
    assert target["node_id"] is None
    assert target["local_key"] == "parent-key"


def test_resolve_child_device_uses_parent_gateway_and_child_key():
    devices = normalize_cloud_devices(
        [
            _device(),
            _device(
                node_id="child-node",
                uuid="child-uuid",
                local_key="child-key",
                category="infrared",
                name="IR module",
                product_name="IR module",
            ),
        ]
    )
    target = resolve_hub_target(devices, "parent-id/child-node", "parent-id")
    assert target["device_id"] == "parent-id"
    assert target["node_id"] == "child-node"
    assert target["local_key"] == "child-key"
    assert target["device_name"] == "IR module"


def test_resolve_direct_gateway_without_parent_selection():
    devices = normalize_cloud_devices([_device()])
    target = resolve_hub_target(devices, "parent-id", "None")
    assert target["device_id"] == "parent-id"
    assert target["node_id"] is None
    assert target["local_key"] == "parent-key"


def test_child_without_parent_gateway_is_rejected():
    devices = normalize_cloud_devices(
        [_device(node_id="child-node", category="infrared")]
    )
    with pytest.raises(ValueError, match="needs_hub"):
        resolve_hub_target(devices, "parent-id/child-node", "None")


def test_onboarding_never_exposes_legacy_cloud_ir_key_templates():
    """Device normalization for onboarding carries connection data, not IR buttons."""
    device = _device(id="yrc11",category="infrared_light",
                     mapping={"PowerOn": {"code": "PowerOn", "values": "secret"}},
                     function={"PowerOn": SimpleNamespace(code="PowerOn")})
    normalized = normalize_cloud_devices([device])
    assert len(normalized) == 1
    assert all("mapping" not in record and "spec_functions" not in record
               for record in normalized.values())
