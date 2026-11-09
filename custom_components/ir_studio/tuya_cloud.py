"""Tuya Sharing SDK helper for native IR hub onboarding only.

The flow mirrors the public Tuya Local setup options while keeping the
resulting IR transport independent of the Tuya Local integration.
"""
from __future__ import annotations

import hashlib
import asyncio
import logging
import re
from typing import Any

_LOGGER = logging.getLogger(__name__)

TUYA_CLIENT_ID = "HA_3y9q4ak7g4ephrvke"
TUYA_SCHEMA = "haauthorize"

HUB_CATEGORIES = {
    "wgsxj", "lyqwg", "bywg", "zigbee", "wg2", "dgnzk", "videohub",
    "xnwg", "qtyycp", "alexa_yywg", "gywg", "cnwg", "wfcon", "wnykq",
}


def normalize_cloud_devices(devices: Any) -> dict[str, dict[str, Any]]:
    """Convert Tuya Sharing SDK devices into a small, stable flow catalogue."""
    values = devices.values() if hasattr(devices, "values") else devices
    result: dict[str, dict[str, Any]] = {}
    for device in values:
        device_id = getattr(device, "id", None)
        if not device_id:
            continue
        node_id = getattr(device, "node_id", "") or ""
        local_key = getattr(device, "local_key", "") or ""
        category = str(getattr(device, "category", "") or "").strip().casefold()
        is_hub = category in HUB_CATEGORIES or not hasattr(device, "local_key")
        child_key = node_id or ((getattr(device, "uuid", "") or "") if not is_hub else "")
        key = f"{device_id}/{child_key}" if child_key else str(device_id)
        result[key] = {
            "category": category,
            "id": str(device_id),
            "ip": getattr(device, "ip", "") or "",
            "local_key": local_key,
            "name": getattr(device, "name", "") or str(device_id),
            "node_id": str(node_id) if node_id else "",
            "online": bool(getattr(device, "online", False)),
            "product_id": getattr(device, "product_id", "") or "",
            "product_name": getattr(device, "product_name", "") or "",
            "uuid": getattr(device, "uuid", "") or "",
            "is_hub": is_hub,
        }
    return result


def resolve_hub_target(
    devices: dict[str, dict[str, Any]], device_key: str, hub_key: str
) -> dict[str, Any]:
    """Resolve a direct device or child device to the parent LAN gateway."""
    device = devices.get(device_key)
    if device is None:
        raise ValueError("invalid_device")

    if hub_key == "None" or (hub_key == device_key and device.get("is_hub")):
        if not device.get("is_hub") and not device.get("ip"):
            raise ValueError("needs_hub")
        target = device
        node_id = None
        local_key = device.get("local_key")
    else:
        if device.get("ip"):
            raise ValueError("does_not_need_hub")
        target = devices.get(hub_key)
        if target is None or not target.get("is_hub"):
            raise ValueError("invalid_hub")
        node_id = device.get("node_id") or device.get("uuid")
        if not node_id:
            raise ValueError("missing_node_id")
        local_key = device.get("local_key") or target.get("local_key")

    if not local_key:
        raise ValueError("missing_local_key")

    return {
        "device_id": target["id"],
        "local_key": local_key,
        "node_id": node_id,
        "device_name": device.get("name") or target.get("name") or target["id"],
        "product_name": device.get("product_name") or target.get("product_name") or "",
    }


CLOUD_AUTH_STORE_KEY = "ir_studio_cloud_auth"
OWN_QR_AUTH_ORIGIN = "ir_studio_qr"


def _has_valid_cloud_auth(auth: Any) -> bool:
    """Validate stored shape without ever logging or exposing token values."""
    return (
        isinstance(auth, dict)
        and auth.get("_ir_studio_auth_origin") == OWN_QR_AUTH_ORIGIN
        and all(isinstance(auth.get(field), str) and auth[field]
                for field in ("user_code", "terminal_id", "endpoint"))
        and isinstance(auth.get("token_info"), dict)
        and all(isinstance(auth["token_info"].get(field), str)
                and auth["token_info"][field]
                for field in ("access_token", "refresh_token"))
    )


async def async_restore_cloud_auth(hass) -> None:
    """Restore the *private* QR session before panel and config flow usage.

    Only sessions explicitly obtained by IR Studio's own QR flow are trusted.
    Old unmarked credentials might have been copied from Tuya Local by previous
    releases; they must be rejected rather than reused or refreshed.
    """
    from homeassistant.helpers.storage import Store

    bucket = hass.data.setdefault("ir_studio_cloud", {})
    if bucket.get("auth_initialized"):
        return
    try:
        store = Store(hass, 1, CLOUD_AUTH_STORE_KEY, private=True)
        saved = await store.async_load()
        auth = saved.get("auth") if isinstance(saved, dict) else None
        own_auth = bucket.get("auth_cache")
        if not _has_valid_cloud_auth(own_auth):
            # In-memory auth from older versions has no verifiable provenance.
            bucket.pop("auth_cache", None)
            own_auth = None
        if auth is not None and not _has_valid_cloud_auth(auth):
            # Purge legacy credentials that might belong to Tuya Local.
            # Never refresh them, even if the old private Store contains them.
            await store.async_save({"auth": None})
            auth = None
        if _has_valid_cloud_auth(own_auth):
            if not _has_valid_cloud_auth(auth):
                await async_persist_cloud_auth(hass, own_auth)
        elif _has_valid_cloud_auth(auth):
            bucket["auth_cache"] = auth
    except Exception as exc:
        _LOGGER.warning("Smart Life session restore failed (%s)", type(exc).__name__)
    bucket["auth_initialized"] = True


async def async_persist_cloud_auth(hass, auth: dict) -> None:
    """Write session to HA's private 0600 Store, never browser/local JSON."""
    from homeassistant.helpers.storage import Store

    if not _has_valid_cloud_auth(auth):
        raise ValueError("Incomplete Smart Life auth session")
    # Snapshot to avoid writing a dict being updated from a Tuya SDK callback.
    snapshot = {**auth, "token_info": dict(auth["token_info"])}
    await Store(hass, 1, CLOUD_AUTH_STORE_KEY, private=True).async_save({
        "auth": snapshot,
    })


def account_session_available(hass) -> bool:
    """Only IR Studio's explicitly authorized QR session is available."""
    own = hass.data.get("ir_studio_cloud", {})
    return bool(
        isinstance(own, dict) and _has_valid_cloud_auth(own.get("auth_cache"))
    )


class TuyaCloud:
    """Small wrapper around the same Tuya Sharing SDK used by Tuya Local."""

    def __init__(self, hass, *, use_cached_session: bool = True):
        from tuya_sharing import LoginControl

        self.hass = hass
        self._login_control = LoginControl()
        self._user_code: str | None = None
        self._qr_token: str | None = None
        self._last_error: dict[str, Any] = {}
        self._store = hass.data.setdefault("ir_studio_cloud", {})
        own_auth = self._store.get("auth_cache") if use_cached_session else None
        self._auth = own_auth if _has_valid_cloud_auth(own_auth) else {}
        if self._auth:
            self._user_code = self._auth.get("user_code")

    @property
    def is_authenticated(self) -> bool:
        return bool(self._auth)

    def logout(self) -> None:
        """Clear IR Studio's cached session without altering Tuya Local."""
        self._store["auth_cache"] = None
        self._auth = {}
        self._user_code = None
        self._qr_token = None

    @property
    def last_error(self) -> dict[str, Any]:
        return dict(self._last_error)

    async def async_get_qr_code(self, user_code: str | None = None) -> str | None:
        """Request a Tuya/Smart Life QR login token."""
        code = (user_code or self._user_code or "").strip()
        if not code:
            self._last_error = {"message": "A Tuya user code is required"}
            return None
        response = await self.hass.async_add_executor_job(
            self._login_control.qr_code, TUYA_CLIENT_ID, TUYA_SCHEMA, code
        )
        if response.get("success", False):
            self._user_code = code
            self._qr_token = response["result"]["qrcode"]
            self._last_error = {}
            return self._qr_token
        self._last_error = {
            "code": response.get("code"),
            "message": response.get("msg", "Unknown Tuya login error"),
        }
        _LOGGER.warning("Tuya QR login token request failed")
        return None

    async def async_login(self) -> bool:
        """Complete QR login after the mobile app has scanned the code."""
        if not self._user_code or not self._qr_token:
            return False
        success, info = await self.hass.async_add_executor_job(
            self._login_control.login_result,
            self._qr_token,
            TUYA_CLIENT_ID,
            self._user_code,
        )
        if not success:
            self._last_error = {
                "code": info.get("code"),
                "message": info.get("msg", "Unknown Tuya login error"),
            }
            # A pending/denied QR must not erase the previous working
            # persisted session. The user can scan a new QR and retry.
            _LOGGER.warning("Tuya QR login was not completed")
            return False

        self._auth = {
            "_ir_studio_auth_origin": OWN_QR_AUTH_ORIGIN,
            "user_code": self._user_code,
            "terminal_id": info["terminal_id"],
            "endpoint": info["endpoint"],
            "token_info": {
                "t": info["t"],
                "uid": info["uid"],
                "expire_time": info["expire_time"],
                "access_token": info["access_token"],
                "refresh_token": info["refresh_token"],
            },
        }
        # A successful login must survive both integration updates and
        # Home Assistant restarts. If disk write fails, do not claim success.
        await async_persist_cloud_auth(self.hass, self._auth)
        self._store["auth_cache"] = self._auth
        self._last_error = {}
        return True

    async def async_get_devices(self) -> dict[str, dict[str, Any]]:
        """Fetch devices and gateway relationships from the Tuya account."""
        from tuya_sharing import Manager, SharingDeviceListener, SharingTokenListener

        if not self._auth:
            raise RuntimeError("Tuya cloud is not authenticated")

        updated_auth = False
        owner = self

        class TokenListener(SharingTokenListener):
            def update_token(self, token_info: dict[str, Any]) -> None:
                nonlocal updated_auth
                if isinstance(token_info, dict) and token_info.get("access_token"):
                    owner._auth["token_info"] = {
                        **owner._auth.get("token_info", {}), **token_info,
                    }
                    owner._store["auth_cache"] = owner._auth
                    updated_auth = True
                _LOGGER.debug("Tuya cloud token refreshed")

        class DeviceListener(SharingDeviceListener):
            def update_device(self, device, updated_status_properties=None) -> None:
                return None

            def add_device(self, device) -> None:
                return None

            def remove_device(self, device_id: str) -> None:
                return None

        manager = Manager(
            TUYA_CLIENT_ID,
            self._auth["user_code"],
            self._auth["terminal_id"],
            self._auth["endpoint"],
            self._auth["token_info"],
            TokenListener(),
        )
        manager.add_device_listener(DeviceListener())
        await self.hass.async_add_executor_job(manager.update_device_cache)
        if updated_auth:
            await async_persist_cloud_auth(self.hass, self._auth)
        devices = normalize_cloud_devices(manager.device_map)
        return devices
