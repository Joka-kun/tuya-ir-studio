"""Experimental local-only Tuya IR transport.

Uses the TinyTuya library directly and does not depend on another Home Assistant
Tuya integration. One instance owns one serialized TinyTuya session; initial handshakes use
Tuya Local's non-persistent defaults before enabling a receive socket.

Hardware status: not yet validated on YRC11. The DPS 201/202 mapping and
payloads follow make-all/tuya-local (MIT, see THIRD_PARTY_NOTICES.md).
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

CMD_STUDY = "study"
CMD_END_STUDY = "study_exit"
CMD_SEND = "send_ir"
MAX_IR_CODE = 24_000
_LOGGER = logging.getLogger(__name__)


def wire_protocol(version: float) -> tuple[float, bool]:
    """Tuya Local's 3.22/3.42/3.52 aliases enable device22 detection.

    TinyTuya does not have wire versions 3.22, 3.42 or 3.52. They
    configure the corresponding real wire protocol plus device22 discovery.
    See make-all/tuya-local: device.py, _rotate_api_protocol_version().
    """
    aliases = {3.22: 3.3, 3.42: 3.4, 3.52: 3.5}
    configured = float(version)
    return aliases.get(configured, configured), configured in aliases


def normalize_node_id(value: Any) -> str | None:
    """Normalize an optional child-device ID from a HA config form."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Node ID must be a string")
    normalized = value.strip()
    return normalized or None


def validate_code(code: str) -> str:
    """Validate an opaque Tuya DP202 payload without changing its contents."""
    if not isinstance(code, str) or not 1 <= len(code) <= MAX_IR_CODE:
        raise ValueError("Invalid IR payload length")
    if any(ord(char) < 32 or ord(char) > 126 for char in code):
        raise ValueError("Invalid IR payload characters")
    return code


def learning_payload(start: bool) -> str:
    return json.dumps(
        {"control": CMD_STUDY if start else CMD_END_STUDY},
        separators=(",", ":"),
    )


def send_payload(code: str, delay_ms: int = 0) -> str:
    validate_code(code)
    if type(delay_ms) is not int or not 0 <= delay_ms <= 10_000:
        raise ValueError("Invalid delay")
    # This wire format is used by make-all/tuya-local remote.py for DP201.
    return json.dumps(
        {
            "control": CMD_SEND,
            "head": "",
            "key1": "1" + code,
            "type": 0,
            "delay": delay_ms,
        },
        separators=(",", ":"),
    )


def extract_learned(data: Any) -> str | None:
    """Extract only an explicit DP202 string; never accept arbitrary DPS."""
    if not isinstance(data, dict) or "Err" in data or "Error" in data:
        return None
    dps = data.get("dps", data)
    if not isinstance(dps, dict):
        return None
    value = dps.get("202", dps.get(202))
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        return None
    return validate_code(value)


async def _await_completion(awaitable):
    """Wait for a blocking operation to finish even if its caller is cancelled.

    Cancelling an asyncio wrapper around run_in_executor does not stop the
    worker thread. Releasing the hub lock while that thread still owns the
    TinyTuya socket would allow study_exit/send to race with receive().
    """
    task = asyncio.ensure_future(awaitable)
    current = asyncio.current_task()
    initial_cancellations = current.cancelling() if current else 0
    interrupted = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            interrupted = True
        except BaseException:
            if current is not None and current.cancelling() > initial_cancellations:
                interrupted = True
            else:
                raise
    cancellation_requested = interrupted or (
        current is not None and current.cancelling() > initial_cancellations
    )
    try:
        result = task.result()
    except BaseException as exc:
        if cancellation_requested:
            raise asyncio.CancelledError from exc
        raise
    if cancellation_requested:
        raise asyncio.CancelledError
    return result


class NativeIRHub:
    """One serialized TinyTuya socket shared by send, learn and ping."""

    def __init__(
        self,
        hass,
        device_id: str,
        host: str,
        local_key: str,
        protocol_version: float = 3.5,
        node_id: str | None = None,
        *,
        device_factory: Callable | None = None,
    ):
        self.hass = hass
        self.device_id = device_id
        self.host = host
        self._key = local_key
        self.protocol = protocol_version
        self.node_id = node_id
        self._factory = device_factory
        self._device = None
        self._lock = asyncio.Lock()
        self.available = False
        self._last_send_at: float | None = None

    def _make_device(self):
        if self._factory is None:
            import tinytuya

            factory = tinytuya.Device
        else:
            factory = self._factory

        # Port the protocol negotiation rules from make-all/tuya-local.
        # In particular 3.42 means version 3.4 with device22 detection ON,
        # not an invalid TinyTuya set_version(3.42).
        version, detect_device22 = wire_protocol(self.protocol)
        if self.node_id:
            parent = factory(self.device_id, self.host, self._key)
            parent.disabledetect = not detect_device22
            parent.set_version(version)
            parent.set_socketRetryLimit(1)
            dev = factory(self.node_id, cid=self.node_id, parent=parent)
        else:
            dev = factory(self.device_id, self.host, self._key)

        dev.disabledetect = not detect_device22
        dev.set_version(version)
        dev.set_socketRetryLimit(1)
        # Match TuyaLocalDevice: TinyTuya's default (non-persistent)
        # socket and default timeout MUST be used for the initial status
        # probe. Turning persistence on before a 3.4/3.5 negotiation
        # changes the original driver's handshake conditions.
        return dev

    @staticmethod
    def _enable_persistent_socket(dev):
        """Only enable the IR receive socket AFTER a valid LAN handshake."""
        parent = getattr(dev, "parent", None)
        if parent is not None:
            parent.set_socketPersistent(True)
        dev.set_socketPersistent(True)

    async def _ensure(self):
        if self._device is None:
            # Keep the constructed object even if cancellation arrives while
            # the executor is creating it; setup/learn cleanup can then close it.
            # Home Assistant returns an asyncio.Future here, not a coroutine.
            # create_task(Future) raises TypeError before any Tuya LAN I/O.
            # ensure_future accepts both HA Futures and coroutine-based fakes
            # while retaining our cancellation-safe completion handling.
            task = asyncio.ensure_future(
                self.hass.async_add_executor_job(self._make_device)
            )
            current = asyncio.current_task()
            initial_cancellations = current.cancelling() if current else 0
            interrupted = False
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    interrupted = True
                except BaseException:
                    if current is not None and current.cancelling() > initial_cancellations:
                        interrupted = True
                    else:
                        raise
            cancellation_requested = interrupted or (
                current is not None and current.cancelling() > initial_cancellations
            )
            try:
                self._device = task.result()
            except BaseException as exc:
                if cancellation_requested:
                    raise asyncio.CancelledError from exc
                raise
            if cancellation_requested:
                raise asyncio.CancelledError
        return self._device

    async def _executor(self, func, *args):
        return await _await_completion(
            self.hass.async_add_executor_job(func, *args)
        )

    async def connect(self):
        async with self._lock:
            try:
                dev = await self._ensure()
                result = await self._executor(dev.status)
                # Same reachability contract as Tuya Local's async_refresh:
                # a real status dictionary, or error 900 (IR/RF devices).
                # None and empty dictionaries are NOT evidence of a handshake.
                if not isinstance(result, dict) or not result:
                    raise ConnectionError("No valid Tuya LAN status response")
                if "Err" in result or "Error" in result:
                    error_code = str(result.get("Err", ""))
                    if error_code != "900":
                        raise ConnectionError(
                            f"Tuya LAN status error {error_code or 'unknown'}"
                        )
                # The original Tuya Local LAN probe has no persistent
                # connection. Our remote needs one only AFTER we have
                # successfully negotiated a session, for DP202 learning.
                await self._executor(self._enable_persistent_socket, dev)
            except asyncio.CancelledError:
                await _await_completion(self._close_unlocked())
                raise
            except Exception as exc:
                try:
                    await _await_completion(self._close_unlocked())
                except Exception:
                    pass
                raise ConnectionError("Local Tuya hub could not be reached") from exc
            self.available = True
            self._last_send_at = None

    async def _close_unlocked(self):
        dev, self._device = self._device, None
        self.available = False
        self._last_send_at = None
        if dev is None:
            return

        async def close_device():
            try:
                await self.hass.async_add_executor_job(
                    dev.set_socketPersistent, False
                )
            finally:
                parent = getattr(dev, "parent", None)
                if parent is not None:
                    await self.hass.async_add_executor_job(
                        parent.set_socketPersistent, False
                    )

        await _await_completion(close_device())

    async def close(self):
        async with self._lock:
            await _await_completion(self._close_unlocked())

    async def _set(self, payload):
        dev = await self._ensure()
        # Tuya Local sends IR study/send commands without awaiting a DPS ack.
        # Waiting for one can consume the unsolicited DP202 IR-learning frame
        # before receive() sees it. TinyTuya uses getresponse=False for nowait.
        result = await self._executor(dev.set_value, 201, payload, True)
        if isinstance(result, dict) and ("Err" in result or "Error" in result):
            raise ConnectionError("Local Tuya write failed")

    @staticmethod
    def _status_is_ready(result) -> bool:
        """A Tuya IR hub may report Err=900 instead of DPS state."""
        if not isinstance(result, dict) or not result:
            return False
        if "Err" in result or "Error" in result:
            return str(result.get("Err", "")) == "900"
        return True

    async def _prepare_send_unlocked(self):
        """Warm an idle LAN session BEFORE transmitting a potentially toggling code.

        The DP201 write is intentionally no-ack. Once written, its outcome is
        unknowable, so retrying it could turn a TV on and immediately off.
        Only the *status probe*, which does not emit IR, may be retried.
        """
        now = asyncio.get_running_loop().time()
        if self._last_send_at is not None and now - self._last_send_at < 30:
            return
        dev = await self._ensure()
        try:
            status = await self._executor(dev.status)
            if not self._status_is_ready(status):
                raise ConnectionError("Stale Tuya IR session")
        except Exception:
            # Complete the old socket teardown before opening a new one.
            await _await_completion(self._close_unlocked())
            dev = await self._ensure()
            try:
                status = await self._executor(dev.status)
                if not self._status_is_ready(status):
                    raise ConnectionError("Unable to reconnect IR hub")
                await self._executor(self._enable_persistent_socket, dev)
            except Exception:
                await _await_completion(self._close_unlocked())
                raise ConnectionError("IR hub unavailable before transmission")

    async def send(self, code: str, delay_ms: int = 0):
        async with self._lock:
            try:
                await self._prepare_send_unlocked()
                await self._set(send_payload(code, delay_ms))
                self._last_send_at = asyncio.get_running_loop().time()
                self.available = True
            except asyncio.CancelledError:
                self.available = False
                await _await_completion(self._close_unlocked())
                raise
            except Exception:
                self.available = False
                await _await_completion(self._close_unlocked())
                raise

    async def learn(self, timeout: int = 30) -> str:
        if type(timeout) is not int or not 10 <= timeout <= 90:
            raise ValueError("Learning timeout must be between 10 and 90 seconds")

        async with self._lock:
            started = False
            close_after = False
            primary_error = None
            try:
                await self._ensure()
                # Set this before set_value: the worker may finish the start
                # command just as the coroutine receives cancellation.
                started = True
                await self._set(learning_payload(True))
                self.available = True

                received_packets = 0
                deadline = asyncio.get_running_loop().time() + timeout
                while asyncio.get_running_loop().time() < deadline:
                    dev = await self._ensure()
                    packet = await self._executor(dev.receive)
                    if isinstance(packet, dict) and packet:
                        received_packets += 1
                    code = extract_learned(packet)
                    if code is not None:
                        # Never log IR payload bytes or Local Key.
                        _LOGGER.info("IR Studio received DP202 (length=%s)", len(code))
                        return code
                    await asyncio.sleep(0.08)
                _LOGGER.warning(
                    "IR Studio learning timed out without DP202 after %ss "
                    "(received packets=%s)",
                    timeout,
                    received_packets,
                )
                raise TimeoutError("No DP202 IR signal received")
            except asyncio.CancelledError as exc:
                primary_error = exc
                if not started:
                    self.available = False
                    await _await_completion(self._close_unlocked())
                raise
            except TimeoutError as exc:
                primary_error = exc
                raise
            except Exception as exc:
                primary_error = exc
                close_after = True
                self.available = False
                raise
            finally:
                if started:
                    try:
                        # Shield the complete cleanup sequence, not just the
                        # executor Future. study_exit must finish before the
                        # hub lock is released to a subsequent send/learn.
                        await _await_completion(
                            self._set(learning_payload(False))
                        )
                    except asyncio.CancelledError:
                        self.available = False
                        await _await_completion(self._close_unlocked())
                        raise
                    except Exception as cleanup_error:
                        self.available = False
                        try:
                            await _await_completion(self._close_unlocked())
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            pass
                        if primary_error is None:
                            raise ConnectionError(
                                "Could not exit IR learning mode"
                            ) from cleanup_error

                if close_after:
                    await _await_completion(self._close_unlocked())
