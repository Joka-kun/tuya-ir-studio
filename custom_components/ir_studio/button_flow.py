"""Native Home Assistant subflow to manage one learned IR command at a time.

Changing the visible caption never modifies the transmitted command namespace.
Tests and re-learning are explicit actions; unknown first sends are never repeated.
"""
from __future__ import annotations

import logging

import voluptuous as vol

from .utils import clean_label

_LOGGER = logging.getLogger(__name__)


class IRButtonFlowMixin:
    """OptionsFlow steps, relying on the main flow's active profile and store."""

    def _button(self):
        if not self._button_id:
            raise ValueError("No button selected")
        return self._runtime.find_button(self._profile(), self._button_id)

    async def async_step_manage_button(self, user_input=None):
        try:
            profile = self._profile()
        except ValueError:
            return self.async_abort(reason="no_profiles")
        choices = {button["id"]: button["name"] for button in profile["buttons"]}
        if not choices:
            return await self.async_step_manage_actions()
        if user_input is not None:
            button_id = user_input.get("button_id")
            if button_id in choices:
                self._button_id = button_id
                return await self.async_step_button_actions()
        return self.async_show_form(
            step_id="manage_button",
            data_schema=vol.Schema({vol.Required("button_id"): vol.In(choices)}),
            errors={"base": "invalid_input"} if user_input is not None else {},
        )

    async def async_step_button_actions(self, user_input=None):
        try:
            self._button()
        except ValueError:
            self._button_id = None
            return await self.async_step_manage_actions()
        return self.async_show_menu(
            step_id="button_actions",
            menu_options=[
                "test_button", "relearn_button", "rename_command",
                "remove_command", "choose_another_button",
            ],
        )

    async def async_step_choose_another_button(self, user_input=None):
        self._button_id = None
        return await self.async_step_manage_button()

    async def async_step_test_button(self, user_input=None):
        """Send exactly once when explicitly confirmed by the user."""
        try:
            profile, button = self._profile(), self._button()
        except ValueError:
            return await self.async_step_manage_actions()
        errors = {}
        if user_input is not None:
            if not user_input.get("confirm", False):
                errors["base"] = "confirmation_required"
            elif button.get("status") == "pending":
                errors["base"] = "not_learned"
            else:
                source = self.hass.states.get(profile["remote_entity"])
                if (not source or source.state not in ("on", "off")
                        or source.attributes.get("ir_studio_virtual")):
                    errors["base"] = "no_hub"
                else:
                    try:
                        await self.hass.services.async_call(
                            "remote", "send_command", {
                                "entity_id": profile["remote_entity"],
                                "device": profile.get("remote_device", profile["name"]),
                                "command": [button.get("remote_name", button["name"])],
                            }, blocking=True,
                        )
                    except Exception:
                        _LOGGER.exception("IR command test could not be transmitted")
                        errors["base"] = "send_failed"
                    else:
                        return await self.async_step_button_actions()
        return self.async_show_form(
            step_id="test_button",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            errors=errors,
        )

    async def async_step_relearn_button(self, user_input=None):
        """Learn again with the same physical command key and stable button ID."""
        try:
            profile, button = self._profile(), self._button()
        except ValueError:
            return await self.async_step_manage_actions()
        errors = {"base": "learn_failed"} if self._learn_failed else {}
        self._learn_failed = False
        if user_input is not None:
            if not user_input.get("confirm", False):
                errors["base"] = "confirmation_required"
            else:
                source = self.hass.states.get(profile["remote_entity"])
                if (not source or source.state not in ("on", "off")
                        or source.attributes.get("ir_studio_virtual")):
                    errors["base"] = "no_hub"
                else:
                    self._relearn_button_id = button["id"]
                    self._command_name = button.get("remote_name", button["name"])
                    self._learn_task = None
                    return await self.async_step_learn()
        return self.async_show_form(
            step_id="relearn_button",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            errors=errors,
        )

    async def async_step_rename_command(self, user_input=None):
        """Edit caption, never mutate recorded IR code or the HA unique ID."""
        try:
            profile, button = self._profile(), self._button()
        except ValueError:
            return await self.async_step_manage_button()
        errors = {}
        if user_input is not None:
            try:
                name = clean_label(user_input["name"])
                runtime = self._runtime
                async with runtime.lock:
                    if any(other["id"] != button["id"] and
                           other["name"].casefold() == name.casefold()
                           for other in profile["buttons"]):
                        errors["name"] = "name_exists"
                    else:
                        original_name = button["name"]
                        original_key = button.get("remote_name")
                        button.setdefault("remote_name", original_name)
                        button["name"] = name
                        try:
                            await runtime.save()
                        except Exception:
                            button["name"] = original_name
                            if original_key is None:
                                button.pop("remote_name", None)
                            raise
                        return await self.async_step_button_actions()
            except (ValueError, KeyError):
                errors["base"] = "invalid_input"
        return self.async_show_form(
            step_id="rename_command",
            data_schema=vol.Schema({
                vol.Required("name", default=button["name"]):
                    self._command_options(),
            }),
            errors=errors,
        )

    async def async_step_remove_command(self, user_input=None):
        """Remove IR Studio metadata, not the physical driver's CodeStore."""
        try:
            profile, button = self._profile(), self._button()
        except ValueError:
            return await self.async_step_manage_button()
        errors = {}
        if user_input is not None:
            if not user_input.get("confirm", False):
                errors["base"] = "confirmation_required"
            else:
                runtime = self._runtime
                async with runtime.lock:
                    # Re-resolve while holding the lock to avoid stale edits.
                    button = runtime.find_button(profile, self._button_id)
                    index = profile["buttons"].index(button)
                    profile["buttons"].pop(index)
                    key = f"{profile['id']}/{button['id']}"
                    raw = runtime.ir_codes.pop(key, None)
                    native = runtime.native_codes.pop(key, None)
                    try:
                        await runtime.save()
                    except Exception:
                        profile["buttons"].insert(index, button)
                        if raw is not None:
                            runtime.ir_codes[key] = raw
                        if native is not None:
                            runtime.native_codes[key] = native
                        raise
                    self._button_id = None
                    return await self.async_step_manage_actions()
        return self.async_show_form(
            step_id="remove_command",
            data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
            errors=errors,
        )
