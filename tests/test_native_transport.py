"""Native Tuya adapter tests with a fake socket: NOT YRC11 verification."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "ir_studio"
sys.modules.setdefault("ir_studio", types.ModuleType("ir_studio"))
sys.modules["ir_studio"].__path__ = [str(ROOT)]
spec = importlib.util.spec_from_file_location("ir_studio.native_transport", ROOT / "native_transport.py")
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)


class DummyHA:
    async def async_add_executor_job(self, func, *args):
        return func(*args)


class DummyTuya:
    def __init__(self, dev_id, host, key):
        self.dev_id, self.host, self.key = dev_id, host, key
        self.calls = []
        self.incoming = [None, {"dps": {"202": "ABCDE12345"}}]
        self.fail_start = False

    def set_version(self, ver):
        self.calls.append(("version", ver))

    def set_socketPersistent(self, enabled):
        self.calls.append(("persist", enabled))

    def set_socketTimeout(self, timeout):
        self.calls.append(("timeout", timeout))

    def set_socketRetryLimit(self, limit):
        self.calls.append(("retries", limit))

    def status(self):
        self.calls.append(("status",))
        return {"dps": {"201": ""}}

    def set_value(self, dp, payload, nowait=False):
        data = json.loads(payload)
        self.calls.append(("set", dp, data))
        self.calls.append(("nowait", nowait))
        if self.fail_start and data.get("control") == "study":
            raise ConnectionError("simulated error")
        return None

    def receive(self):
        self.calls.append(("receive",))
        return self.incoming.pop(0) if self.incoming else None



def test_normalize_optional_node_id():
    assert transport.normalize_node_id(None) is None
    assert transport.normalize_node_id("") is None
    assert transport.normalize_node_id("   ") is None
    assert transport.normalize_node_id("  child-node  ") == "child-node"


def test_normalize_node_id_rejects_non_string_values():
    with pytest.raises(ValueError, match="Node ID must be a string"):
        transport.normalize_node_id(123)


@pytest.mark.parametrize("status", [{"Err": "900", "Error": "Data unvalid"}, {"Err": 900, "Error": "Data unvalid"}, {"dps": {}}])
@pytest.mark.asyncio
async def test_ir_status_without_state_is_a_reachable_handshake(status):
    fake = DummyTuya("device", "host", "secret")
    fake.status = lambda: status
    hub = transport.NativeIRHub(
        DummyHA(), "device", "host", "secret", device_factory=lambda *args: fake
    )
    await hub.connect()
    assert hub.available is True
    await hub.close()


@pytest.mark.parametrize(
    "status",
    [
        {"Err": "901", "Error": "Network Error"},
        {"Error": "Unexpected status failure"},
    ],
)
@pytest.mark.asyncio
async def test_non_900_status_errors_still_fail_connection(status):
    fake = DummyTuya("device", "host", "secret")
    fake.status = lambda: status
    hub = transport.NativeIRHub(
        DummyHA(), "device", "host", "secret", device_factory=lambda *args: fake
    )
    with pytest.raises(ConnectionError):
        await hub.connect()
    assert hub.available is False


def test_dp201_wire_payloads():
    assert transport.learning_payload(True) == '{"control":"study"}'
    assert transport.learning_payload(False) == '{"control":"study_exit"}'
    obj = json.loads(transport.send_payload("ABCDE12345"))
    assert obj == {"control": "send_ir", "head": "", "key1": "1ABCDE12345", "type": 0, "delay": 0}


@pytest.mark.parametrize("invalid", ["", "\n", "bad\x00data", 123, "a" * 24001])
def test_refuse_bad_code(invalid):
    with pytest.raises(ValueError):
        transport.validate_code(invalid)


@pytest.mark.parametrize("packet", [None, {}, {"dps": {"202": None}}, {"dps": {"201": "OTHER"}}, {"Err": "904", "dps": {"202": "STALE"}}])
def test_extract_ignores_non_dp202(packet):
    assert transport.extract_learned(packet) is None


def test_extract_from_numeric_or_text_key():
    assert transport.extract_learned({"dps": {202: "A==="}}) == "A==="
    assert transport.extract_learned({"202": "QQ=="}) == "QQ=="


@pytest.mark.asyncio
async def test_learn_sends_study_receives_dp202_and_exits():
    fake = DummyTuya("device", "127.0.0.1", "key")
    hub = transport.NativeIRHub(DummyHA(), "device", "127.0.0.1", "key", device_factory=lambda *args: fake)
    await hub.connect()
    assert await hub.learn(timeout=10) == "ABCDE12345"
    assert [x[2]["control"] for x in fake.calls if x[0] == "set"] == ["study", "study_exit"]
    await hub.send("ABCDE12345")
    outgoing = [x[2] for x in fake.calls if x[0] == "set"][-1]
    assert outgoing["control"] == "send_ir"
    await hub.close()
    assert ("persist", False) in fake.calls
    assert fake.key == "key" and hub.available is False


@pytest.mark.asyncio
async def test_error_during_study_closes_connection_without_claiming_available():
    fake = DummyTuya("device", "host", "secret")
    fake.fail_start = True
    hub = transport.NativeIRHub(DummyHA(), "device", "host", "secret", device_factory=lambda *args: fake)
    await hub.connect()
    with pytest.raises(ConnectionError):
        await hub.learn(timeout=10)
    assert not hub.available
    assert not any(x[0] == "receive" for x in fake.calls)


@pytest.mark.asyncio
async def test_concurrent_send_waits_for_learning_lock():
    fake = DummyTuya("device", "host", "secret")
    hub = transport.NativeIRHub(DummyHA(), "device", "host", "secret", device_factory=lambda *args: fake)
    await hub.connect()
    await asyncio.gather(hub.learn(10), hub.send("A123"))
    actions = [x[2]["control"] for x in fake.calls if x[0] == "set"]
    assert actions in (["study", "study_exit", "send_ir"], ["send_ir", "study", "study_exit"])

class BlockingReceiveHA(DummyHA):
    """Executor fake whose receive operation can be held in flight."""

    def __init__(self):
        self.receive_started = asyncio.Event()
        self.release_receive = asyncio.Event()
        self.receive_error = None

    async def async_add_executor_job(self, func, *args):
        if getattr(func, "__name__", "") == "receive":
            self.receive_started.set()
            await self.release_receive.wait()
            if self.receive_error is not None:
                raise self.receive_error
        return func(*args)


@pytest.mark.asyncio
async def test_cancelled_receive_finishes_before_study_exit_and_next_send():
    hass = BlockingReceiveHA()
    fake = DummyTuya("device", "host", "secret")
    hub = transport.NativeIRHub(
        hass, "device", "host", "secret", device_factory=lambda *args: fake
    )
    await hub.connect()

    learn_task = asyncio.create_task(hub.learn(timeout=10))
    await asyncio.wait_for(hass.receive_started.wait(), timeout=1)
    learn_task.cancel()

    send_task = asyncio.create_task(hub.send("A123"))
    await asyncio.sleep(0)
    assert not send_task.done()

    # The cancelled caller must not release the hub lock while receive() is
    # still running in the executor.
    hass.release_receive.set()
    with pytest.raises(asyncio.CancelledError):
        await learn_task
    await send_task

    actions = [call[2]["control"] for call in fake.calls if call[0] == "set"]
    assert actions == ["study", "study_exit", "send_ir"]
    assert not hub._lock.locked()
    assert hub.available is True


@pytest.mark.asyncio
async def test_cancelled_receive_preserves_cancellation_if_executor_fails():
    hass = BlockingReceiveHA()
    hass.receive_error = OSError("simulated socket failure")
    fake = DummyTuya("device", "host", "secret")
    hub = transport.NativeIRHub(
        hass, "device", "host", "secret", device_factory=lambda *args: fake
    )
    await hub.connect()

    learn_task = asyncio.create_task(hub.learn(timeout=10))
    await asyncio.wait_for(hass.receive_started.wait(), timeout=1)
    learn_task.cancel()
    hass.release_receive.set()

    with pytest.raises(asyncio.CancelledError):
        await learn_task
    actions = [call[2]["control"] for call in fake.calls if call[0] == "set"]
    assert actions == ["study", "study_exit"]
    assert not hub._lock.locked()



@pytest.mark.parametrize("status", [None, {}, False, "not-a-dictionary"])
@pytest.mark.asyncio
async def test_no_status_response_is_not_a_successful_gateway_registration(status):
    """Tuya Local requires returned state; do not accept failed TCP handshakes."""
    fake = DummyTuya("device", "host", "secret")
    fake.status = lambda: status
    hub = transport.NativeIRHub(
        DummyHA(), "device", "host", "secret",
        device_factory=lambda *args: fake,
    )
    with pytest.raises(ConnectionError, match="Local Tuya hub could not be reached"):
        await hub.connect()
    assert hub.available is False


@pytest.mark.parametrize(
    ("configured", "wire_version", "device22"),
    [(3.3, 3.3, False), (3.4, 3.4, False), (3.5, 3.5, False),
     (3.22, 3.3, True), (3.42, 3.4, True), (3.52, 3.5, True)],
)
def test_tuya_local_protocol_aliases(configured, wire_version, device22):
    """3.22 / 3.42 / 3.52 are not actual wire versions."""
    assert transport.wire_protocol(configured) == (wire_version, device22)
    fake = DummyTuya("device", "host", "secret")
    hub = transport.NativeIRHub(
        DummyHA(), "device", "host", "secret", configured,
        device_factory=lambda *args: fake,
    )
    assert hub._make_device() is fake
    assert ("version", wire_version) in fake.calls
    assert fake.disabledetect is (not device22)


@pytest.mark.parametrize("configured", [3.4, 3.42])
def test_parent_and_child_use_the_same_wire_negotiation(configured):
    """Subdevice's TinyTuya parent must match its effective protocol."""
    instances = []

    class GatewayDevice(DummyTuya):
        def __init__(self, dev_id, host=None, key=None, *, cid=None, parent=None):
            super().__init__(dev_id, host, key)
            self.cid, self.parent = cid, parent
            instances.append(self)

    hub = transport.NativeIRHub(
        DummyHA(), "parent", "192.168.2.110", "secret", configured, "child",
        device_factory=GatewayDevice,
    )
    child = hub._make_device()
    parent = child.parent
    expected, detect = transport.wire_protocol(configured)
    assert child.cid == "child"
    assert parent.dev_id == "parent"
    assert ("version", expected) in parent.calls
    assert ("version", expected) in child.calls
    assert parent.disabledetect is (not detect)
    assert child.disabledetect is (not detect)
    assert ("retries", 1) in parent.calls
    assert ("retries", 1) in child.calls



@pytest.mark.asyncio
async def test_registration_uses_tuya_local_default_session_during_status():
    """Regression: IR Studio 0.5.9 forced a 2s timeout and persistent socket."""
    class StrictGateway(DummyTuya):
        def status(self):
            self.calls.append(("status",))
            if ("persist", True) in self.calls or ("timeout", 2) in self.calls:
                return {"Err": "914", "Error": "Session negotiation failed"}
            return {"Err": "900", "Error": "No status DPS for IR gateway"}

    fake = StrictGateway("gateway", "192.168.2.110", "key")
    hub = transport.NativeIRHub(
        DummyHA(), "gateway", "192.168.2.110", "key",
        3.4, device_factory=lambda *args: fake,
    )
    await hub.connect()
    assert hub.available is True
    assert ("timeout", 2) not in fake.calls
    assert fake.calls.index(("status",)) < fake.calls.index(("persist", True))
    await hub.close()
    assert fake.calls[-1] == ("persist", False)


@pytest.mark.asyncio
async def test_child_tuya_local_probe_uses_fresh_nonpersistent_parent():
    """A child CID must not force the parent's socket persistent before status."""
    created = []

    class StrictChild(DummyTuya):
        def __init__(self, dev_id, host=None, key=None, *, cid=None, parent=None):
            super().__init__(dev_id, host, key)
            self.parent = parent
            self.cid = cid
            created.append(self)

        def status(self):
            self.calls.append(("status",))
            parent = self.parent
            if parent is None:
                return {"Err": "914", "Error": "Not a child"}
            if any(("persist", True) in d.calls for d in (self, parent)):
                return {"Err": "914", "Error": "Premature persistent socket"}
            return {"Err": "900", "Error": "IR child has no state"}

    hub = transport.NativeIRHub(
        DummyHA(), "gateway", "192.168.2.110", "key",
        3.42, "child-cid", device_factory=StrictChild,
    )
    await hub.connect()
    parent, child = created
    assert child.parent is parent
    assert parent.dev_id == "gateway"
    assert child.cid == "child-cid"
    assert ("version", 3.4) in parent.calls
    assert ("persist", True) in parent.calls
    assert ("persist", True) in child.calls
    await hub.close()
    assert ("persist", False) in parent.calls
    assert ("persist", False) in child.calls



class FutureReturningHA:
    """Emulate actual Home Assistant async_add_executor_job (asyncio.Future)."""

    def async_add_executor_job(self, func, *args):
        return asyncio.get_running_loop().run_in_executor(None, func, *args)


@pytest.mark.asyncio
async def test_home_assistant_executor_future_connects_before_status():
    """Real regression from HA log: create_task(Future) raised TypeError.

    Unlike DummyHA (which has an async def), Home Assistant's method
    returns a Future immediately. This test must exercise that production
    contract, not just mocks returning coroutines.
    """
    hass = FutureReturningHA()
    device = DummyTuya("gateway", "192.168.2.110", "dummy-key")
    hub = transport.NativeIRHub(
        hass,
        "gateway",
        "192.168.2.110",
        "dummy-key",
        3.5,
        device_factory=lambda *args: device,
    )
    await hub.connect()
    assert hub.available
    assert ("status",) in device.calls
    await hub.send("ABCDE12345")
    assert any(call[0] == "set" for call in device.calls)
    await hub.close()
    assert hub.available is False
    assert ("persist", False) in device.calls


@pytest.mark.asyncio
async def test_home_assistant_executor_future_supports_ir900_handshake():
    hass = FutureReturningHA()
    device = DummyTuya("gateway", "192.168.2.110", "dummy-key")
    device.status = lambda: {"Err": "900", "Error": "IR has no status DPS"}
    hub = transport.NativeIRHub(
        hass,
        "gateway",
        "192.168.2.110",
        "dummy-key",
        3.4,
        device_factory=lambda *args: device,
    )
    await hub.connect()
    assert hub.available
    await hub.close()



@pytest.mark.asyncio
async def test_learn_preserves_dp202_when_dp201_has_no_response_wait():
    """Regression: blocking TinyTuya set_value consumed the first DP202 event."""
    class IrSignalDuringWrite(DummyTuya):
        def __init__(self, *args):
            super().__init__(*args)
            self.incoming = []

        def set_value(self, dp, payload, nowait=False):
            data = json.loads(payload)
            self.calls.append(("set", dp, data))
            self.calls.append(("nowait", nowait))
            if data.get("control") == "study":
                # A first received packet can arrive immediately after study.
                # The old getresponse=True call consumed it as a write ack.
                if not nowait:
                    return {"dps": {"202": "FASTSIGNAL"}}
                self.incoming.append({"dps": {"202": "FASTSIGNAL"}})
            return None

    device = IrSignalDuringWrite("gateway", "192.168.2.110", "dummy-key")
    hub = transport.NativeIRHub(
        FutureReturningHA(), "gateway", "192.168.2.110",
        "dummy-key", 3.5, device_factory=lambda *args: device,
    )
    await hub.connect()
    learned = await hub.learn(timeout=10)
    await hub.send(learned)
    await hub.close()
    assert learned == "FASTSIGNAL"
    assert all(call == ("nowait", True) for call in device.calls if call[0] == "nowait")
    assert [x[2]["control"] for x in device.calls if x[0] == "set"] == [
        "study", "study_exit", "send_ir",
    ]


@pytest.mark.asyncio
async def test_dp201_error_return_is_not_reported_as_success():
    device = DummyTuya("gateway", "192.168.2.110", "dummy-key")
    device.set_value = lambda dp, payload, nowait=False: {
        "Err": "914", "Error": "Session negotiation failed",
    }
    hub = transport.NativeIRHub(
        FutureReturningHA(), "gateway", "192.168.2.110",
        "dummy-key", 3.5, device_factory=lambda *args: device,
    )
    await hub.connect()
    with pytest.raises(ConnectionError, match="Local Tuya write failed"):
        await hub.send("ABCDE12345")
    assert hub.available is False



@pytest.mark.asyncio
async def test_first_ir_send_preflights_idle_session_without_repeating_payload():
    """No-ack DP201 must not run on an unverified cold session."""
    device = DummyTuya("test", "127.0.0.1", "secret")
    hub = transport.NativeIRHub(
        DummyHA(), "test", "127.0.0.1", "secret",
        device_factory=lambda *args: device,
    )
    await hub.connect()
    assert device.calls.count(("status",)) == 1
    await hub.send("AAAAA")
    assert device.calls.count(("status",)) == 2
    assert len([x for x in device.calls if x[0] == "set"
                and x[2].get("control") == "send_ir"]) == 1
    await hub.send("BBBBB")
    # Next command inside the warm window need not renegotiate.
    assert device.calls.count(("status",)) == 2
    assert len([x for x in device.calls if x[0] == "set"
                and x[2].get("control") == "send_ir"]) == 2


@pytest.mark.asyncio
async def test_stale_socket_preflight_reconnects_before_first_ir_write():
    first = DummyTuya("test", "host", "key")
    second = DummyTuya("test", "host", "key")
    original = first.status
    checks = 0

    def status():
        nonlocal checks
        checks += 1
        return original() if checks == 1 else {}

    first.status = status
    devices = iter((first, second))
    hub = transport.NativeIRHub(
        DummyHA(), "test", "host", "key",
        device_factory=lambda *args: next(devices),
    )
    await hub.connect()
    await hub.send("ABCDE")
    assert ("persist", False) in first.calls
    assert ("status",) in second.calls
    assert [v[2]["control"] for v in first.calls if v[0] == "set"] == []
    assert [v[2]["control"] for v in second.calls if v[0] == "set"] == ["send_ir"]


@pytest.mark.asyncio
async def test_unavailable_hub_preflight_never_transmits_unknown_command():
    first = DummyTuya("test", "host", "key")
    second = DummyTuya("test", "host", "key")
    checks = 0
    def status():
        nonlocal checks
        checks += 1
        return {"dps": {}} if checks == 1 else None
    first.status = status
    second.status = lambda: None
    devices = iter((first, second))
    hub = transport.NativeIRHub(
        DummyHA(), "test", "host", "key",
        device_factory=lambda *args: next(devices),
    )
    await hub.connect()
    with pytest.raises(ConnectionError, match="IR hub unavailable"):
        await hub.send("ABCDE")
    assert not any(x[0] == "set" for x in first.calls + second.calls)
    assert hub.available is False
