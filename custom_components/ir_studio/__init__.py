"""Local IR Studio panel, native Tuya IR hubs, and compatible Home Assistant remotes.

Existing Home Assistant remote bindings remain supported. New physical Tuya
hubs are configured as first-class native LAN config entries.
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
import time
import uuid

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import DOMAIN, FRONTEND_URL, FRONTEND_VERSION, PANEL_PATH, SIGNAL_CHANGED, STORAGE_KEY, STORAGE_VERSION
from .templates import validate_template_catalog, upgrade_library_button_labels
from .icons import validate_icon_catalog
from .legacy_cleanup import clean_cloud_placeholders

from .websocket import register_commands
from .tuya_cloud import async_restore_cloud_auth

_LOGGER = logging.getLogger(__name__)


def _read_static_catalog(filename: str) -> dict:
    """Read a bundled JSON catalog in HA's executor, never in its event loop."""
    path = Path(__file__).with_name(filename)
    return json.loads(path.read_text(encoding="utf-8"))


def _profile_owner_entry_id(hass) -> str | None:
    """Choose one active owner, never an unreachable or disabled gateway.

    Keep the chosen owner for this runtime to avoid duplicate profile entities
    when additional config entries are loaded later.
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    candidates = [
        e for e in entries
        if getattr(e, "disabled_by", None) is None
        and getattr(getattr(e, "state", None), "value", getattr(e, "state", None))
        in (None, "loaded", "setup_in_progress")
    ]
    runtime = hass.data.get(DOMAIN)
    saved = getattr(runtime, "profile_owner_entry_id", None)
    if saved and any(e.entry_id == saved for e in candidates):
        return saved
    managers = sorted(e.entry_id for e in candidates
                      if e.data.get("kind") != "native_hub")
    natives = sorted(e.entry_id for e in candidates
                     if e.data.get("kind") == "native_hub")
    chosen = (managers or natives or [None])[0]
    if runtime is not None:
        runtime.profile_owner_entry_id = chosen
    return chosen


class StudioRuntime:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self.storage = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.code_storage = Store(hass, 1, "ir_studio_imported_ir")
        self.ir_codes: dict[str, str] = {}
        self.native_code_storage = Store(hass, 1, "ir_studio_imported_tuya_dp202")
        self.native_codes: dict[str, str] = {}
        self.native_hubs: dict[str, object] = {}
        self.native_remotes: dict[str, object] = {}
        self.active_entries: set[str] = set()
        self.profile_owner_entry_id: str | None = None
        self.profiles: list[dict] = []
        self.jobs: dict[str, dict] = {}
        self.job_tasks: dict[str, asyncio.Task] = {}
        self.lock = asyncio.Lock()
        self.presets: dict[str, list[str]] = {}
        self.template_catalog: dict = {}
        self.icons: list[dict] = []
        self.panel_registered = False
        self.panel_lock = asyncio.Lock()

    async def load(self):
        raw = await self.storage.async_load() or {}
        self.profiles = raw.get("profiles", [])
        self.ir_codes = await self.code_storage.async_load() or {}
        self.native_codes = await self.native_code_storage.async_load() or {}
        # The obsolete cloud import created speculative, unlearned buttons.
        # Keep every learned/verified command, and clean only placeholders.
        removed, empty = clean_cloud_placeholders(
            self.profiles, self.ir_codes, self.native_codes)
        if removed or empty:
            await self.storage.async_save({"profiles": self.profiles})
            _LOGGER.info(
                "IR Studio migrated obsolete cloud-name placeholders "
                "(buttons=%d, empty_profiles=%d)", removed, empty)
        # The icon library is presentation-only and never participates in IR
        # code lookup. Its stable identifiers also serve old stored type IDs.
        icon_catalog = await self.hass.async_add_executor_job(
            _read_static_catalog, "icon_catalog.json"
        )
        self.icons = validate_icon_catalog(icon_catalog)
        # Presets contain only names, not raw IR signals, keys, device IDs or API tokens.
        catalog = await self.hass.async_add_executor_job(
            _read_static_catalog, "presets.json"
        )
        if isinstance(catalog, dict) and catalog.get("schema_version") == 2:
            self.template_catalog = validate_template_catalog(catalog)
            self.presets = {}
        else:
            # Backward compatibility with the old name-keyed preset format.
            self.presets = catalog
            self.template_catalog = {}
        # Convert only unchanged Russian names created by IR Studio's own
        # library. Never rename custom labels or the learned Remote code key.
        renamed = upgrade_library_button_labels(self.profiles, self.template_catalog)
        if renamed:
            await self.storage.async_save({"profiles": self.profiles})

    async def save(self):
        await self.code_storage.async_save(self.ir_codes)
        await self.native_code_storage.async_save(self.native_codes)
        await self.storage.async_save({"profiles": self.profiles})
        async_dispatcher_send(self.hass, SIGNAL_CHANGED)

    def find_profile(self, profile_id: str) -> dict:
        for profile in self.profiles:
            if profile["id"] == profile_id:
                return profile
        raise ValueError("Профиль не найден")

    def find_button(self, profile: dict, button_id: str) -> dict:
        for button in profile["buttons"]:
            if button["id"] == button_id:
                return button
        raise ValueError("Команда не найдена")

    def new_job(self, kind: str, profile_id: str, button_id: str) -> str:
        entity_id = self.find_profile(profile_id)["remote_entity"]
        if any(j["status"] in ("running", "cancelling") and j["remote_entity"] == entity_id
               for j in self.jobs.values()):
            raise ValueError("Этот физический Remote уже выполняет операцию. Дождись окончания")
        job_id = uuid.uuid4().hex
        self.jobs[job_id] = {
            "id": job_id, "kind": kind, "profile_id": profile_id,
            "button_id": button_id, "remote_entity": entity_id, "status": "running", "message": "Ожидание ответа Home Assistant…",
            "started_at": time.time(),
        }
        # Bound the in-memory jobs list. Completed jobs can be removed; active ones can't.
        if len(self.jobs) > 100:
            for key in list(self.jobs):
                if len(self.jobs) <= 80:
                    break
                if self.jobs[key]["status"] != "running":
                    self.jobs.pop(key, None)
        return job_id


async def _async_cleanup_runtime_if_unused(hass: HomeAssistant) -> None:
    """Remove shared panel/runtime resources after the last entry is gone."""
    runtime: StudioRuntime | None = hass.data.get(DOMAIN)
    if runtime is None or runtime.active_entries:
        return

    tasks = list(runtime.job_tasks.values())
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    for hub in tuple(runtime.native_hubs.values()):
        try:
            await hub.close()
        except Exception:
            _LOGGER.debug("Failed to close a native IR hub during cleanup", exc_info=True)
    runtime.native_hubs.clear()

    if runtime.panel_registered:
        frontend.async_remove_panel(hass, PANEL_PATH)
        runtime.panel_registered = False
    hass.data.pop(DOMAIN, None)


async def _async_sync_optional_panel(hass: HomeAssistant, runtime: StudioRuntime) -> None:
    """Keep the legacy editor optional; new installs have no sidebar link.

    An entry with missing show_panel is a pre-existing installation and retains
    the old sidebar until its owner explicitly switches it off. New native hub
    entries have show_panel=False by default.
    """
    async with runtime.panel_lock:
        configured = hass.config_entries.async_entries(DOMAIN)
        visible = any(
            getattr(entry, "disabled_by", None) is None
            and entry.options.get("show_panel", True)
            for entry in configured
        )
        if visible and not runtime.panel_registered:
            if not hass.data.get(f"{DOMAIN}_static_paths_registered"):
                await hass.http.async_register_static_paths(
                    [
                        StaticPathConfig(FRONTEND_URL, str(Path(__file__).parent / "frontend" / "panel.js"), False),
                        StaticPathConfig("/ir_studio_static/icon.png", str(Path(__file__).parent / "frontend" / "icon.png"), False),
                    ]
                )
                hass.data[f"{DOMAIN}_static_paths_registered"] = True
            await panel_custom.async_register_panel(
                hass=hass,
                webcomponent_name="ir-studio-panel",
                frontend_url_path=PANEL_PATH,
                module_url=f"{FRONTEND_URL}?v={FRONTEND_VERSION}",
                sidebar_title="Tuya IR Studio",
                sidebar_icon="mdi:remote",
                require_admin=True,
            )
            runtime.panel_registered = True
        elif not visible and runtime.panel_registered:
            frontend.async_remove_panel(hass, PANEL_PATH)
            runtime.panel_registered = False


async def _async_panel_options_changed(hass: HomeAssistant, entry) -> None:
    """Update panel visibility without reloading the physical IR gateway."""
    runtime = hass.data.get(DOMAIN)
    if runtime is not None:
        await _async_sync_optional_panel(hass, runtime)


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    # Migrate older panel-only entries. New setup creates native_hub entries
    # directly; existing manager entries remain loadable for compatibility.
    if entry.data.get("kind") != "native_hub" and entry.title == "Tuya IR Studio":
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, "kind": "manager"},
            title="Tuya IR Studio — Панель",
        )

    from .native_transport import NativeIRHub

    runtime = hass.data.get(DOMAIN)
    if runtime is None:
        # The device-name cache is persisted already; restore the matching
        # private QR auth before the first WebSocket request after HA restart.
        await async_restore_cloud_auth(hass)
        runtime = StudioRuntime(hass)
        await runtime.load()
        hass.data[DOMAIN] = runtime

    # Home Assistant also runs these callbacks when setup raises, including
    # ConfigEntryNotReady. This prevents a half-created shared panel/runtime.
    entry.async_on_unload(lambda: _async_cleanup_runtime_if_unused(hass))

    entry.async_on_unload(entry.add_update_listener(_async_panel_options_changed))
    await _async_sync_optional_panel(hass, runtime)

    if not hass.data.get(f"{DOMAIN}_commands_registered"):
        register_commands(hass)
        hass.data[f"{DOMAIN}_commands_registered"] = True

    if entry.data.get("kind") == "native_hub":
        hub = NativeIRHub(
            hass,
            entry.data["device_id"],
            entry.data["host"],
            entry.data["local_key"],
            float(entry.data.get("protocol_version", "3.5")),
            entry.data.get("node_id") or None,
        )
        # Register cleanup before the first network await. HA invokes it if
        # setup is retried or cancelled before the platform is forwarded.
        entry.async_on_unload(hub.close)
        try:
            await hub.connect()
        except (ConnectionError, OSError):
            from homeassistant.exceptions import ConfigEntryNotReady

            raise ConfigEntryNotReady("Native Tuya IR hub unreachable") from None

        runtime.native_hubs[entry.entry_id] = hub
        try:
            await hass.config_entries.async_forward_entry_setups(entry, ["remote", "button"])
        except Exception:
            runtime.native_hubs.pop(entry.entry_id, None)
            await hub.close()
            raise
    else:
        await hass.config_entries.async_forward_entry_setups(entry, ["remote", "button"])

    runtime.active_entries.add(entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    runtime: StudioRuntime | None = hass.data.get(DOMAIN)
    if runtime is None:
        return True

    platforms = ["remote", "button"]
    unloaded = await hass.config_entries.async_unload_platforms(entry, platforms)
    if not unloaded:
        return False

    hub = runtime.native_hubs.pop(entry.entry_id, None)
    if hub:
        await hub.close()

    runtime.active_entries.discard(entry.entry_id)
    if runtime.profile_owner_entry_id == entry.entry_id:
        runtime.profile_owner_entry_id = None
        # Reload an already-active peer to take over virtual profile entities
        # after an owner removal, without deleting any physical IR codes.
        if runtime.active_entries:
            replacement = sorted(runtime.active_entries)[0]
            hass.async_create_task(hass.config_entries.async_reload(replacement))
    await _async_cleanup_runtime_if_unused(hass)
    return True
