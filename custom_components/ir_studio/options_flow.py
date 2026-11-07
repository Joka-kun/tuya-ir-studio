"""Native Home Assistant options wizard for IR Studio profiles and commands.

The panel is an optional advanced editor. Every everyday operation here writes
the same runtime Store as the existing panel and emits the same dispatcher
updates, so existing entity unique IDs and learned code keys never change.
"""
from __future__ import annotations

import asyncio
import logging
import uuid

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import IconSelector, SelectSelector, SelectSelectorConfig, SelectSelectorMode

from .button_flow import IRButtonFlowMixin
from .icon_mdi import validate_mdi_icon
from .const import DOMAIN
from .utils import clean_label

_LOGGER = logging.getLogger(__name__)
_MAX_PROFILES = 24
_MAX_BUTTONS = 200


class IRStudioOptionsFlow(IRButtonFlowMixin, config_entries.OptionsFlow):
    """Built-in Configure wizard: create, learn, manage and hide advanced panel."""

    def __init__(self):
        self._profile_id: str | None = None
        self._command_name: str | None = None
        self._button_id: str | None = None
        self._relearn_button_id: str | None = None
        self._learn_task: asyncio.Task | None = None
        self._learn_failed = False

    @property
    def _runtime(self):
        return self.hass.data.get(DOMAIN)

    def _physical_remotes(self) -> dict[str, str]:
        """Return live, nonvirtual HA transmitters, including idle 'off'."""
        result = {}
        for state in self.hass.states.async_all("remote"):
            if state.state not in ("on", "off"):
                continue
            if state.attributes.get("ir_studio_virtual"):
                continue
            result[state.entity_id] = state.attributes.get("friendly_name") or state.entity_id
        return dict(sorted(result.items()))

    def _default_remote(self, remotes: dict[str, str]) -> str:
        runtime = self._runtime
        if runtime:
            for entity_id, entity in runtime.native_remotes.items():
                if (entity_id in remotes
                        and getattr(getattr(entity, "_entry", None), "entry_id", None)
                        == self.config_entry.entry_id):
                    return entity_id
        return next(iter(remotes), "")

    def _profile(self):
        if self._runtime is None or not self._profile_id:
            raise ValueError("Profile no longer available")
        return self._runtime.find_profile(self._profile_id)

    def _command_options(self, *, custom_value: bool = True):
        """Searchable English labels from the canonical command library.

        This selector only suggests command *names*. It does not attach a
        template, fabricate signals or alter any code-store keys.
        """
        commands = self._runtime.template_catalog.get("commands", {})
        names = sorted({
            item["labels"]["en"]
            for item in commands.values()
            if item.get("labels", {}).get("en")
        }, key=str.casefold)
        return SelectSelector(SelectSelectorConfig(
            options=[{"value": value, "label": value} for value in names],
            custom_value=custom_value,
            mode=SelectSelectorMode.DROPDOWN,
        ))

    def _icon_options(self):
        """Native Home Assistant visual icon picker with real previews."""
        return IconSelector()

    _validated_mdi = staticmethod(validate_mdi_icon)

    def _icon_from_profile(self, profile):
        direct = profile.get("icon_mdi")
        if isinstance(direct, str) and direct.startswith("mdi:"):
            return direct
        return "mdi:" + next(
            (item["mdi"] for item in self._runtime.icons
             if item["id"] == profile.get("icon")), "remote"
        )

    def _apply_icon(self, profile, mdi):
        mdi = self._validated_mdi(mdi)
        profile["icon_mdi"] = mdi
        matching = next(
            (item["id"] for item in self._runtime.icons
             if "mdi:" + item["mdi"] == mdi), None
        )
        profile["icon"] = matching or "blank_remote"

    def _finish(self):
        return self.async_abort(reason="saved")

    async def async_step_init(self, user_input=None):
        if self._runtime is None:
            return self.async_abort(reason="not_ready")
        actions = ["create_remote"]
        if self._runtime.profiles:
            actions.append("manage_remote")
        actions.append("interface")
        return self.async_show_menu(step_id="init", menu_options=actions)

    async def async_step_create_remote(self, user_input=None):
        runtime = self._runtime
        if runtime is None:
            return self.async_abort(reason="not_ready")
        remotes = self._physical_remotes()
        if not remotes:
            return self.async_abort(reason="no_hub")
        errors = {}
        if user_input is not None:
            try:
                name = clean_label(user_input["name"], limit=64)
                source = user_input.get("remote_entity") or self._default_remote(remotes)
                if source not in remotes:
                    raise ValueError("Invalid hub")
                icon = self._validated_mdi(user_input.get("icon") or "mdi:remote")
                async with runtime.lock:
                    if len(runtime.profiles) >= _MAX_PROFILES:
                        errors["base"] = "limit_reached"
                    elif any(p["name"].casefold() == name.casefold() for p in runtime.profiles):
                        errors["name"] = "name_exists"
                    else:
                        profile = {
                            "id": uuid.uuid4().hex, "name": name,
                            "remote_device": name, "remote_entity": source,
                            "buttons": [], "template_id": "", "profile_type": "",
                            "icon": "blank_remote", "button_origin": "manual",
                        }
                        self._apply_icon(profile, icon)
                        runtime.profiles.append(profile)
                        try:
                            await runtime.save()
                        except Exception:
                            runtime.profiles.remove(profile)
                            raise
                        self._profile_id = profile["id"]
                        return await self.async_step_manage_actions()
            except (ValueError, KeyError):
                errors["base"] = "invalid_input"

        fields = {
            vol.Required("name"): str,
            vol.Optional("icon", default="mdi:remote"): self._icon_options(),
        }
        if len(remotes) > 1:
            fields[vol.Required(
                "remote_entity", default=self._default_remote(remotes)
            )] = vol.In(remotes)
        return self.async_show_form(
            step_id="create_remote",
            data_schema=vol.Schema(fields), errors=errors,
            description_placeholders={"hub": remotes[self._default_remote(remotes)]},
        )

    async def async_step_manage_remote(self, user_input=None):
        runtime = self._runtime
        if runtime is None or not runtime.profiles:
            return self.async_abort(reason="no_profiles")
        if user_input is not None:
            pid = user_input.get("profile_id")
            if any(p["id"] == pid for p in runtime.profiles):
                self._profile_id = pid
                return await self.async_step_manage_actions()
        choices = {p["id"]: p["name"] for p in runtime.profiles}
        return self.async_show_form(
            step_id="manage_remote",
            data_schema=vol.Schema({vol.Required("profile_id"): vol.In(choices)}),
        )

    async def async_step_manage_actions(self, user_input=None):
        try:
            self._profile()
        except ValueError:
            return self.async_abort(reason="no_profiles")
        actions = ["add_command", "rename_remote"]
        if self._profile()["buttons"]:
            actions.append("manage_button")
        actions.extend(["change_icon", "remove_remote", "finish"])
        return self.async_show_menu(
            step_id="manage_actions", menu_options=actions,
        )

    async def async_step_finish(self, user_input=None):
        return self._finish()

    async def async_step_add_command(self, user_input=None):
        try:
            profile = self._profile()
        except ValueError:
            return self.async_abort(reason="no_profiles")
        errors = {"base": "learn_failed"} if self._learn_failed else {}
        self._learn_failed = False
        if user_input is not None:
            try:
                name = clean_label(user_input["name"])
                if len(profile["buttons"]) >= _MAX_BUTTONS:
                    errors["base"] = "limit_reached"
                elif any(
                    b["name"].casefold() == name.casefold()
                    or b.get("remote_name", b["name"]).casefold() == name.casefold()
                    for b in profile["buttons"]
                ):
                    errors["name"] = "name_exists"
                else:
                    source = self.hass.states.get(profile["remote_entity"])
                    if not source or source.state not in ("on", "off") or source.attributes.get("ir_studio_virtual"):
                        errors["base"] = "no_hub"
                    else:
                        self._command_name = name
                        self._relearn_button_id = None
                        self._learn_task = None
                        return await self.async_step_learn()
            except (ValueError, KeyError):
                errors["base"] = "invalid_input"
        return self.async_show_form(
            step_id="add_command",
            data_schema=vol.Schema({
                vol.Required("name"): self._command_options(),
            }),
            errors=errors,
        )

    async def _async_learn(self) -> None:
        """No runtime lock held across remote.learn_command (it uses that lock)."""
        runtime = self._runtime
        profile = self._profile()
        source = profile["remote_entity"]
        code_key = self._command_name
        if not runtime or not code_key:
            raise ValueError("Missing learning target")
        state = self.hass.states.get(source)
        if not state or state.state not in ("on", "off") or state.attributes.get("ir_studio_virtual"):
            raise ValueError("Physical remote unavailable")
        remote_device = profile.get("remote_device", profile["name"])
        # The HA action controls local transport. No invented IR payloads.
        await asyncio.wait_for(
            self.hass.services.async_call(
                "remote", "learn_command",
                {
                    "entity_id": source, "device": remote_device,
                    "command": [code_key], "command_type": "ir", "timeout": 60,
                },
                blocking=True,
            ),
            timeout=80,
        )
        async with runtime.lock:
            profile = self._profile()
            target = (
                runtime.find_button(profile, self._relearn_button_id)
                if self._relearn_button_id else None
            )
            if any(
                b is not target and
                b.get("remote_name", b["name"]).casefold() == code_key.casefold()
                for b in profile["buttons"]
            ):
                raise ValueError("Command already exists")
            item = target if target is not None else {
                "id": uuid.uuid4().hex, "name": code_key,
                "remote_name": code_key, "origin": "manual",
                "status": "needs_check", "verified": False,
            }
            # Known native/tuya_ir stores expose learned codes before the
            # service returns. Unknown third-party drivers cannot be assumed
            # to persist their raw IR waveform.
            from .websocket import _known_code
            known = _known_code(self.hass, profile, item)
            registry_entry = er.async_get(self.hass).async_get(source)
            # Tuya Local confirms its DP202 store before returning.
            new_status = ("stored" if known or (
                registry_entry and registry_entry.platform == "tuya_local"
            ) else "needs_check")
            if target is None:
                item["status"] = new_status
                profile["buttons"].append(item)
            else:
                previous = (item["status"], item.get("verified", False))
                item["status"] = new_status
                item["verified"] = False
            try:
                await runtime.save()
            except Exception:
                if target is None:
                    profile["buttons"].remove(item)
                else:
                    item["status"], item["verified"] = previous
                raise

    async def async_step_learn(self, user_input=None):
        if self._learn_task is None:
            self._learn_task = self.hass.async_create_task(self._async_learn())
        if not self._learn_task.done():
            return self.async_show_progress(
                step_id="learn", progress_action="learn",
                progress_task=self._learn_task,
            )
        return self.async_show_progress_done(next_step_id="learn_done")

    async def async_step_learn_done(self, user_input=None):
        if self._learn_task is None:
            return self.async_abort(reason="not_ready")
        try:
            self._learn_task.result()
        except (Exception, asyncio.CancelledError) as exc:
            _LOGGER.warning("Native IR command learning failed: %s", type(exc).__name__)
            self._learn_task = None
            self._learn_failed = True
            if self._relearn_button_id:
                return await self.async_step_relearn_button()
            return await self.async_step_add_command()
        self._learn_task = None
        if self._relearn_button_id:
            self._relearn_button_id = None
            return await self.async_step_button_actions()
        return await self.async_step_manage_actions()

    async def async_step_rename_remote(self, user_input=None):
        try:
            profile = self._profile()
        except ValueError:
            return self.async_abort(reason="no_profiles")
        errors = {}
        if user_input is not None:
            try:
                name = clean_label(user_input["name"], limit=64)
                runtime = self._runtime
                async with runtime.lock:
                    if any(p["id"] != profile["id"] and p["name"].casefold() == name.casefold()
                           for p in runtime.profiles):
                        errors["name"] = "name_exists"
                    else:
                        former = profile["name"]
                        profile.setdefault("remote_device", former)
                        profile["name"] = name
                        try:
                            await runtime.save()
                        except Exception:
                            profile["name"] = former
                            raise
                        return await self.async_step_manage_actions()
            except (KeyError, ValueError):
                errors["base"] = "invalid_input"
        return self.async_show_form(
            step_id="rename_remote",
            data_schema=vol.Schema({vol.Required("name", default=profile["name"]): str}),
            errors=errors,
        )


    async def async_step_change_icon(self, user_input=None):
        """Native MDI picker supplies a real visual preview of the icon."""
        try:
            profile = self._profile()
        except ValueError:
            return self.async_abort(reason="no_profiles")
        errors = {}
        if user_input is not None:
            try:
                icon = self._validated_mdi(user_input.get("icon"))
            except ValueError:
                errors["icon"] = "invalid_input"
            else:
                async with self._runtime.lock:
                    previous_icon = profile.get("icon")
                    previous_mdi = profile.get("icon_mdi")
                    self._apply_icon(profile, icon)
                    try:
                        await self._runtime.save()
                    except Exception:
                        if previous_icon is None:
                            profile.pop("icon", None)
                        else:
                            profile["icon"] = previous_icon
                        if previous_mdi is None:
                            profile.pop("icon_mdi", None)
                        else:
                            profile["icon_mdi"] = previous_mdi
                        raise
                return await self.async_step_manage_actions()
        return self.async_show_form(
            step_id="change_icon",
            data_schema=vol.Schema({
                vol.Required("icon", default=self._icon_from_profile(profile)):
                    self._icon_options(),
            }),
            errors=errors,
        )

    async def async_step_remove_remote(self, user_input=None):
        try:
            profile = self._profile()
        except ValueError:
            return self.async_abort(reason="no_profiles")
        errors = {}
        if user_input is not None:
            if not user_input.get("confirm"):
                errors["base"] = "confirmation_required"
            else:
                runtime = self._runtime
                async with runtime.lock:
                    if any(job.get("profile_id") == profile["id"]
                           and job.get("status") in ("running", "cancelling")
                           for job in runtime.jobs.values()):
                        errors["base"] = "busy"
                    else:
                        original_profiles = list(runtime.profiles)
                        raw_codes = dict(runtime.ir_codes)
                        native_codes = dict(runtime.native_codes)
                        runtime.profiles.remove(profile)
                        prefix = f"{profile['id']}/"
                        runtime.ir_codes = {k: v for k, v in runtime.ir_codes.items()
                                            if not k.startswith(prefix)}
                        runtime.native_codes = {k: v for k, v in runtime.native_codes.items()
                                                if not k.startswith(prefix)}
                        try:
                            await runtime.save()
                        except Exception:
                            runtime.profiles = original_profiles
                            runtime.ir_codes = raw_codes
                            runtime.native_codes = native_codes
                            raise
                        self._profile_id = None
                        return self._finish()
        return self.async_show_form(
            step_id="remove_remote",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            description_placeholders={"name": profile["name"]}, errors=errors,
        )

    async def async_step_interface(self, user_input=None):
        if user_input is not None:
            options = dict(self.config_entry.options)
            options["show_panel"] = bool(user_input["show_panel"])
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="interface",
            data_schema=vol.Schema({
                vol.Required(
                    "show_panel",
                    default=self.config_entry.options.get("show_panel", True),
                ): bool,
            }),
        )
