"""Persistent Tuya Sharing SDK auth: reboot recovery, token rotation, no erasure."""
import importlib.util
from pathlib import Path
import sys
import types

import pytest


ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "ir_studio"
spec = importlib.util.spec_from_file_location("ir_studio_cloud_auth_test", ROOT / "tuya_cloud.py")
cloud_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cloud_module)


def creds(access="access-old", refresh="refresh-old"):
    return {
        "user_code": "user-code", "terminal_id": "terminal",
        "endpoint": "https://tuya.example.invalid",
        "token_info": {
            "access_token": access, "refresh_token": refresh,
            "t": 100, "uid": "user", "expire_time": 100000,
        },
    }


@pytest.fixture
def fake_storage(monkeypatch):
    storage_db = {}
    invocations = []

    class FakeStore:
        def __init__(self, hass, version, key, *, private=False):
            assert version == 1
            self.key = key
            invocations.append((key, private))
            if key == cloud_module.CLOUD_AUTH_STORE_KEY:
                assert private is True

        async def async_load(self):
            return storage_db.get(self.key)

        async def async_save(self, payload):
            storage_db[self.key] = payload

    ha = types.ModuleType("homeassistant")
    ha.__path__ = []
    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    storage = types.ModuleType("homeassistant.helpers.storage")
    storage.Store = FakeStore
    monkeypatch.setitem(sys.modules, "homeassistant", ha)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers", helpers)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.storage", storage)
    return storage_db, invocations


@pytest.mark.asyncio
async def test_successful_login_persists_and_restores_after_restart(fake_storage):
    saved, invocations = fake_storage
    auth = creds()
    hass1 = types.SimpleNamespace(data={"ir_studio_cloud": {"auth_cache": auth}})
    await cloud_module.async_persist_cloud_auth(hass1, auth)
    assert cloud_module.CLOUD_AUTH_STORE_KEY in saved
    # Simulated Home Assistant restart: hass.data is newly empty.
    hass2 = types.SimpleNamespace(data={})
    await cloud_module.async_restore_cloud_auth(hass2)
    assert hass2.data["ir_studio_cloud"]["auth_cache"] == auth
    assert bool(hass2.data["ir_studio_cloud"]["auth_cache"])
    assert (cloud_module.CLOUD_AUTH_STORE_KEY, True) in invocations
    # Two-phase restore must not erase previously authenticated session.
    await cloud_module.async_restore_cloud_auth(hass2)
    assert hass2.data["ir_studio_cloud"]["auth_cache"] == auth


@pytest.mark.asyncio
async def test_legacy_in_memory_and_existing_tuya_local_sessions_are_migrated(fake_storage):
    saved, _ = fake_storage
    auth = creds()
    hass = types.SimpleNamespace(data={"ir_studio_cloud": {"auth_cache": auth}})
    await cloud_module.async_restore_cloud_auth(hass)
    assert saved[cloud_module.CLOUD_AUTH_STORE_KEY]["auth"] == auth
    saved.clear()
    shared = types.SimpleNamespace(data={"tuya_local": {"auth_cache": auth}})
    await cloud_module.async_restore_cloud_auth(shared)
    assert shared.data["ir_studio_cloud"]["auth_cache"] == auth
    assert saved[cloud_module.CLOUD_AUTH_STORE_KEY]["auth"] == auth


@pytest.mark.asyncio
async def test_failed_qr_confirmation_does_not_logout_old_session(fake_storage, monkeypatch):
    saved, _ = fake_storage
    auth = creds()
    await cloud_module.async_persist_cloud_auth(types.SimpleNamespace(data={}), auth)

    class LoginControl:
        def login_result(self, *args):
            return False, {"code": 1110, "msg": "QR is not confirmed"}

    tuya_sharing = types.ModuleType("tuya_sharing")
    tuya_sharing.LoginControl = LoginControl
    monkeypatch.setitem(sys.modules, "tuya_sharing", tuya_sharing)
    async def executor(job, *args):
        return job(*args)
    hass = types.SimpleNamespace(data={"ir_studio_cloud": {"auth_cache": auth}},
                                 async_add_executor_job=executor)
    client = cloud_module.TuyaCloud(hass, use_tuya_local_cache=False)
    client._user_code = "user-code"
    client._qr_token = "pending-qr"
    assert await client.async_login() is False
    assert hass.data["ir_studio_cloud"]["auth_cache"] == auth
    assert saved[cloud_module.CLOUD_AUTH_STORE_KEY]["auth"] == auth


@pytest.mark.asyncio
async def test_successful_qr_login_writes_tokens_before_responding(fake_storage, monkeypatch):
    saved, _ = fake_storage
    class LoginControl:
        def login_result(self, *args):
            return True, {
                "terminal_id": "new-terminal", "endpoint": "https://example.invalid",
                "t": 200, "uid": "uid", "expire_time": 200000,
                "access_token": "access-new", "refresh_token": "refresh-new",
            }
    tuya_sharing = types.ModuleType("tuya_sharing")
    tuya_sharing.LoginControl = LoginControl
    monkeypatch.setitem(sys.modules, "tuya_sharing", tuya_sharing)
    async def executor(job, *args):
        return job(*args)
    hass = types.SimpleNamespace(data={}, async_add_executor_job=executor)
    client = cloud_module.TuyaCloud(hass, use_tuya_local_cache=False)
    client._user_code = "user-code"
    client._qr_token = "approved-token"
    assert await client.async_login()
    assert saved[cloud_module.CLOUD_AUTH_STORE_KEY]["auth"]["token_info"]["access_token"] == "access-new"
    assert hass.data["ir_studio_cloud"]["auth_cache"]["terminal_id"] == "new-terminal"


@pytest.mark.asyncio
async def test_sdk_token_refresh_persists_updated_access_and_refresh(fake_storage, monkeypatch):
    saved, _ = fake_storage

    class LoginControl:
        pass

    class SharingTokenListener:
        pass

    class SharingDeviceListener:
        pass

    class Manager:
        def __init__(self, client_id, user_code, terminal_id, endpoint, token_info, listener):
            self.listener = listener
            self.device_map = {}
            self.customer_api = types.SimpleNamespace(get=lambda _url: {"success": True})
        def add_device_listener(self, listener):
            pass
        def update_device_cache(self):
            self.listener.update_token({
                "access_token": "access-rotated", "refresh_token": "refresh-rotated"
            })

    sharing = types.ModuleType("tuya_sharing")
    sharing.LoginControl = LoginControl
    sharing.SharingTokenListener = SharingTokenListener
    sharing.SharingDeviceListener = SharingDeviceListener
    sharing.Manager = Manager
    monkeypatch.setitem(sys.modules, "tuya_sharing", sharing)
    async def executor(job, *args):
        return job(*args)
    hass = types.SimpleNamespace(
        data={"ir_studio_cloud": {"auth_cache": creds()}},
        async_add_executor_job=executor,
    )
    client = cloud_module.TuyaCloud(hass)
    assert await client.async_get_devices() == {}
    token = saved[cloud_module.CLOUD_AUTH_STORE_KEY]["auth"]["token_info"]
    assert token["access_token"] == "access-rotated"
    assert token["refresh_token"] == "refresh-rotated"
    assert token["uid"] == "user"
