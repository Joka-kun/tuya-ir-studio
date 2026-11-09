"""Regression tests for Tuya account onboarding and panel behavior."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "ir_studio"


def test_ir_studio_manifest_and_native_transport_dependency():
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["integration_type"] == "service"
    assert "tinytuya==1.20.0" in manifest.get("requirements", [])
    assert "tuya-device-sharing-sdk~=0.2.4" in manifest.get("requirements", [])


def test_first_setup_shows_tuya_local_style_setup_choice():
    flow = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
    user_step = flow.split("async def async_step_user", 1)[1].split(
        "def _mark_existing_devices", 1
    )[0]
    assert 'vol.Required("setup_mode", default="cloud")' in user_step
    assert 'options=["cloud", "manual", "cloud_fresh_login"]' in user_step
    assert "SelectSelectorMode.LIST" in user_step
    assert "TuyaCloud(" in user_step
    assert "async_create_entry" not in user_step
    assert "async_step_native_hub()" in user_step
    assert "async_step_cloud()" in user_step


def test_account_flow_has_qr_device_selection_and_lan_discovery():
    flow = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
    assert "async_step_cloud" in flow
    assert "async_step_scan" in flow
    assert "async_step_choose_device" in flow
    assert "async_step_search" in flow
    assert "resolve_hub_target" in flow
    assert "tinytuya.find_device" in flow
    assert "TuyaCloud" in flow


def test_native_hub_flow_uses_tuya_local_local_field_order():
    flow = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
    positions = [
        flow.index('vol.Required("device_id"'),
        flow.index('vol.Required("host"'),
        flow.index('vol.Required("local_key"'),
        flow.index('"protocol_version",\n                default=protocol_default'),
        flow.index('vol.Optional("device_cid"'),
    ]
    assert positions == sorted(positions)
    assert 'vol.Required("poll_only"' not in flow


def test_no_automatic_panel_only_entry_is_created():
    flow = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
    assert 'title="Tuya IR Studio", data={}' not in flow
    assert "one_ir_studio" not in flow
    assert '"kind": "native_hub"' in flow


def test_first_run_has_no_external_tuya_handoff_or_panel_only_branch():
    flow = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8").lower()
    assert "next_flow" not in flow
    assert "panel_only" not in flow


def test_panel_has_no_tuya_local_cta_or_redirect():
    panel = (INTEGRATION / "frontend" / "panel.js").read_text(encoding="utf-8")
    assert 'data-action="open-tuya-local"' not in panel
    assert "open-tuya-local" not in panel
    assert "Открыть Tuya Local" not in panel
    assert "my.home-assistant.io/redirect/config_flow_start" not in panel


def test_idle_remote_off_is_not_marked_disconnected():
    panel = (INTEGRATION / "frontend" / "panel.js").read_text(encoding="utf-8")
    assert "['on', 'off'].includes(remoteState)" in panel
    assert "['on', 'off'].includes(state)" in panel


def test_remote_icon_picker_separates_visual_icon_from_commands():
    panel = (INTEGRATION / "frontend" / "panel.js").read_text(encoding="utf-8")
    ws = (INTEGRATION / "websocket.py").read_text(encoding="utf-8")
    icons = json.loads((INTEGRATION / "icon_catalog.json").read_text(encoding="utf-8"))["icons"]
    assert len(icons) == 200
    assert 'id="preset"' not in panel
    assert 'id="${h(prefix)}-icon"' in panel
    assert 'data-action="choose-icon"' in panel
    assert "SIMPLE_PROFILE_TYPES" not in panel
    assert 'ws_profile_set_icon' in ws
    assert 'vol.Optional("icon"): str' in ws
    assert "color-scheme:" in panel


def test_tuya_cloud_flow_uses_own_private_session_and_sharing_sdk():
    flow = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
    cloud = (INTEGRATION / "tuya_cloud.py").read_text(encoding="utf-8")
    assert "TuyaCloud" in flow
    assert "async_step_scan" in flow
    assert "LoginControl" in cloud
    assert "use_cached_session=" in flow
    assert 'hass.data.get("tuya_local")' not in cloud
    assert 'hass.data.get("ir_studio_cloud")' in cloud
    assert "CLOUD_AUTH_STORE_KEY" in cloud
    assert "Manager(" in cloud


def test_existing_external_remote_entities_remain_compatible():
    websocket = (INTEGRATION / "websocket.py").read_text(encoding="utf-8")
    assert 'and entity_source != "tuya_local"' in websocket
    assert "Tuya Local сохранила DP202-код" in websocket


def test_legacy_panel_entries_remain_loadable_but_new_flow_creates_hubs():
    flow = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
    setup = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
    assert '"kind": "native_hub"' in flow
    assert 'title="Tuya IR Studio — Панель"' in setup
    assert 'data={**entry.data, "kind": "manager"}' in setup
    assert 'data={"kind": "manager"}' not in flow


def test_no_remote_state_explains_setup_without_a_second_integration_link():
    panel = (INTEGRATION / "frontend" / "panel.js").read_text(encoding="utf-8")
    assert "Нет локальных remote-сущностей — сначала добавь ИК-драйвер в Home Assistant" in panel
    assert "open-tuya-local" not in panel


def test_manifest_release_version_and_frontend_cache_version():
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    constants = (INTEGRATION / "const.py").read_text(encoding="utf-8")
    version = manifest["version"]
    assert isinstance(version, str) and len(version.split(".")) == 3
    assert all(part.isdigit() for part in version.split("."))
    assert f'FRONTEND_VERSION = "{version}"' in constants
    assert manifest["categories"] == ["buttons_remotes"]


def test_native_hub_translation_fields_match_tuya_local_local_step():
    expected_fields = [
        "device_id",
        "host",
        "local_key",
        "protocol_version",
        "device_cid",
    ]
    for language in ("en", "ru"):
        strings = json.loads(
            (INTEGRATION / "translations" / f"{language}.json").read_text(
                encoding="utf-8"
            )
        )
        actual_fields = list(strings["config"]["step"]["native_hub"]["data"])
        assert actual_fields == expected_fields


def test_tuya_local_probe_keeps_upstream_retries_and_alias_handling():
    flow = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
    native = (INTEGRATION / "native_transport.py").read_text(encoding="utf-8")
    assert "attempts = 6 if version in (3.22, 3.42, 3.52) else 3" in flow
    assert "aliases = {3.22: 3.3, 3.42: 3.4, 3.52: 3.5}" in native
    assert "parent.disabledetect = not detect_device22" in native
    assert 'raise ConnectionError("No valid Tuya LAN status response")' in native



def test_config_flow_uses_native_transport_with_upstream_socket_defaults():
    native = (INTEGRATION / "native_transport.py").read_text(encoding="utf-8")
    assert "dev.set_socketRetryLimit(1)" in native
    assert "parent.set_socketRetryLimit(1)" in native
    assert "await self._executor(self._enable_persistent_socket, dev)" in native
    assert "dev.set_socketTimeout(2)" not in native
    assert "parent.set_socketTimeout(2)" not in native


def test_native_connection_supports_home_assistant_future_executor():
    native = (INTEGRATION / "native_transport.py").read_text(encoding="utf-8")
    assert "asyncio.ensure_future(" in native
    assert "self.hass.async_add_executor_job(self._make_device)" in native
    assert "asyncio.create_task(\n                self.hass.async_add_executor_job" not in native



def test_learning_is_inline_cancellable_with_60_second_default():
    panel = (INTEGRATION / "frontend" / "panel.js").read_text(encoding="utf-8")
    websocket = (INTEGRATION / "websocket.py").read_text(encoding="utf-8")
    runtime = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
    assert "data-action=\"cancel-job\"" in panel
    assert "class=\"learn-seconds\"" in panel
    assert "const timeout = 60;" in panel
    assert "_showLearnModal(" not in panel
    assert "_showWaiting(" not in panel
    assert "ws_job_cancel" in websocket
    assert 'vol.Optional("timeout", default=60)' in websocket
    assert '("running", "cancelling")' in runtime


def test_legacy_placeholder_cleanup_never_clears_unverified_signals():
    ws = (INTEGRATION / "websocket.py").read_text(encoding="utf-8")
    panel = (INTEGRATION / "frontend" / "panel.js").read_text(encoding="utf-8")
    assert 'vol.Required("type"): "ir_studio/profile_remove_unlearned"' in ws
    assert "ws_profile_remove_unlearned" in ws
    assert "if _known_code(hass, profile, button) is not False:" in ws
    assert "if key in runtime.ir_codes or key in runtime.native_codes:" in ws
    assert 'data-action="review-unlearned"' in panel
    assert 'data-cleanup-id=' in panel


def test_command_cards_share_the_same_visual_design_tokens():
    panel = (INTEGRATION / "frontend" / "panel.js").read_text(encoding="utf-8")
    assert ".item{border:1px solid" in panel
    assert ".cloud-key-choice" in panel
    assert "var(--primary-color" in panel
    assert "@media(max-width:700px)" in panel


def test_qr_parent_gateway_selector_has_configured_hub_fallback():
    flow = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
    # The first dropdown intentionally excludes existing config entries.
    assert 'if device.get("exists") or not device.get("local_key")' in flow
    # The parent gateway dropdown uses cloud hubs and existing HA gateway
    # entries if the QR listing consists only of child IR devices.
    assert 'configured_hub:{entry.entry_id}' in flow
    assert '"is_hub": True' in flow
    assert '"exists": True' in flow
    assert 'hub_options.append(' in flow
    assert 'resolve_hub_target(' in flow



