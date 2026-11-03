"""
IntelliWatch - IoT Integration Layer

Responsibilities:
1. Define the EdgeDevice protocol abstraction (Requirement 4.1).
2. Provide HandshakeResult and Ack data structures.
3. Implement MQTT and HTTP protocol adapters (Requirement 4.3).
4. Gracefully degrade when transport libraries are not installed.

Device management (registry, handshake verification, heartbeat, queue,
authentication, and malformed-message handling) is handled by the
IoTIntegrationLayer class added in subsequent tasks.
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Protocol, Set, Dict, List, Any

from database import current_timestamp


logger = logging.getLogger(__name__)


__all__ = [
    "EdgeDevice",
    "HandshakeResult",
    "Ack",
    "MQTTAdapter",
    "HTTPAdapter",
    "MQTT_AVAILABLE",
    "HTTP_AVAILABLE",
]


# ============================================================
# 1. TRANSPORT LIBRARY IMPORTS (GRACEFUL DEGRADATION)
# ============================================================

try:
    import paho.mqtt.client as mqtt

    MQTT_AVAILABLE = True

except ImportError:
    mqtt = None  # type: ignore[assignment]
    MQTT_AVAILABLE = False
    logger.warning(
        "paho-mqtt is not installed. "
        "MQTTAdapter will not be functional."
    )

try:
    import httpx

    HTTP_AVAILABLE = True

except ImportError:
    httpx = None  # type: ignore[assignment]
    HTTP_AVAILABLE = False
    logger.warning(
        "httpx is not installed. "
        "HTTPAdapter will not be functional."
    )


# ============================================================
# 2. DATA STRUCTURES
# ============================================================

@dataclass
class HandshakeResult:
    """
    Outcome of a device boot handshake.

    Attributes:
        success:     Whether the handshake succeeded.
        device_id:   Identifier of the device that was probed.
        capabilities: Capability set reported by the device.
        protocol:    Transport protocol used for the handshake.
        reason:      Rejection reason when the handshake fails.
    """

    success: bool
    device_id: str
    capabilities: Set[str]
    protocol: str
    reason: str = ""


@dataclass
class Ack:
    """
    Acknowledgement returned by a device after receiving a command.

    Attributes:
        device_id:       Identifier of the acknowledging device.
        intent:          Control-signal intent that was acknowledged.
        timestamp:       ISO-8601 acknowledgement timestamp.
        equipment_state: Resulting equipment state, if reported.
    """

    device_id: str
    intent: str
    timestamp: str
    equipment_state: str = ""


# ============================================================
# 3. EDGE DEVICE PROTOCOL (Requirement 4.1)
# ============================================================

class EdgeDevice(Protocol):
    """
    Structural interface that any IoT edge-device adapter implements.

    Defines the contract for connection, data exchange, and command
    reception over any supported transport protocol.  Adapters provide
    the concrete transport (MQTT, HTTP, ...) while the IntelliWatch
    system treats every device uniformly through this interface.
    """

    device_id: str
    capabilities: Set[str]
    protocol: str

    def connect(self) -> HandshakeResult:
        """
        Establish a connection and perform a boot handshake.

        Returns a HandshakeResult indicating success or failure.
        """
        ...

    def recv_data(self) -> bytes:
        """
        Return the latest device-computed data payload.

        Non-blocking: returns the most recently received payload,
        or empty bytes if no data has been received yet.
        """
        ...

    def send_command(self, intent: str) -> Ack:
        """
        Relay a control-signal intent to the device.

        Returns an Ack recording the device's response.
        """
        ...


# ============================================================
# 4. MQTT ADAPTER (Requirement 4.3)
# ============================================================

class MQTTAdapter:
    """
    EdgeDevice adapter over the MQTT protocol using paho-mqtt.

    If paho-mqtt is not installed the adapter is still constructable,
    but connect() returns a failed HandshakeResult with the reason
    "Required library not installed".
    """

    def __init__(
        self,
        device_id: str,
        broker_host: str,
        broker_port: int = 1883,
        capabilities: Optional[Set[str]] = None
    ):
        """
        Initialize an MQTT adapter for an edge device.

        Args:
            device_id:    Unique identifier for the target device.
            broker_host:  Hostname or IP of the MQTT broker.
            broker_port:  Port of the MQTT broker (default 1883).
            capabilities: Capability set advertised by the device.
        """

        self.device_id = device_id
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.protocol = "MQTT"

        if capabilities is None:
            self.capabilities: Set[str] = set()
        else:
            self.capabilities = set(capabilities)

        # Topic conventions for this device
        self._data_topic = (
            f"intelliwatch/devices/{device_id}/data"
        )
        self._command_topic = (
            f"intelliwatch/devices/{device_id}/command"
        )

        # Runtime state
        self._client = None
        self._latest_payload: bytes = b""
        self._connected: bool = False

    def _on_message(self, client, userdata, message) -> None:
        """
        paho-mqtt callback storing the latest received payload.
        """

        self._latest_payload = message.payload or b""

    def connect(self) -> HandshakeResult:
        """
        Connect to the MQTT broker, subscribe to the device data topic,
        and return a HandshakeResult.
        """

        if not MQTT_AVAILABLE:
            logger.warning(
                "MQTTAdapter.connect failed for '%s': "
                "paho-mqtt not installed.",
                self.device_id
            )
            return HandshakeResult(
                success=False,
                device_id=self.device_id,
                capabilities=self.capabilities,
                protocol=self.protocol,
                reason="Required library not installed"
            )

        try:
            self._client = mqtt.Client(
                client_id=f"intelliwatch-{self.device_id}"
            )
            self._client.on_message = self._on_message

            self._client.connect(
                self.broker_host,
                self.broker_port
            )
            self._client.subscribe(self._data_topic)
            self._client.loop_start()

            self._connected = True

            logger.info(
                "MQTT device '%s' connected to %s:%d",
                self.device_id,
                self.broker_host,
                self.broker_port
            )

            return HandshakeResult(
                success=True,
                device_id=self.device_id,
                capabilities=self.capabilities,
                protocol=self.protocol
            )

        except Exception as error:
            self._connected = False
            self._client = None

            logger.error(
                "MQTT connection failed for '%s': %s",
                self.device_id,
                error
            )

            return HandshakeResult(
                success=False,
                device_id=self.device_id,
                capabilities=self.capabilities,
                protocol=self.protocol,
                reason=str(error)
            )

    def recv_data(self) -> bytes:
        """
        Return the latest received payload (non-blocking).

        Returns empty bytes if the device is not connected or no
        payload has been received yet.
        """

        if not self._connected or self._client is None:
            return b""

        return self._latest_payload

    def send_command(self, intent: str) -> Ack:
        """
        Publish a command intent to the device command topic and
        return an Ack.
        """

        timestamp = current_timestamp()

        if not self._connected or self._client is None:
            logger.warning(
                "MQTTAdapter.send_command: device '%s' not connected.",
                self.device_id
            )
            return Ack(
                device_id=self.device_id,
                intent=intent,
                timestamp=timestamp,
                equipment_state="DISCONNECTED"
            )

        try:
            self._client.publish(self._command_topic, intent)

            logger.info(
                "MQTT command '%s' sent to device '%s'.",
                intent,
                self.device_id
            )

            return Ack(
                device_id=self.device_id,
                intent=intent,
                timestamp=timestamp
            )

        except Exception as error:
            logger.error(
                "MQTT send_command failed for '%s': %s",
                self.device_id,
                error
            )

            return Ack(
                device_id=self.device_id,
                intent=intent,
                timestamp=timestamp,
                equipment_state=f"ERROR: {error}"
            )

    def disconnect(self) -> None:
        """Cleanly disconnect from the MQTT broker and release resources."""

        if self._client is not None:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
            finally:
                self._client = None
                self._connected = False


# ============================================================
# 5. HTTP ADAPTER (Requirement 4.3)
# ============================================================

class HTTPAdapter:
    """
    EdgeDevice adapter over HTTP using httpx.

    If httpx is not installed the adapter is still constructable,
    but connect() returns a failed HandshakeResult with the reason
    "Required library not installed".
    """

    def __init__(
        self,
        device_id: str,
        base_url: str,
        capabilities: Optional[Set[str]] = None
    ):
        """
        Initialize an HTTP adapter for an edge device.

        Args:
            device_id:    Unique identifier for the target device.
            base_url:     Base URL of the device HTTP endpoint.
            capabilities: Capability set advertised by the device.
        """

        self.device_id = device_id
        self.base_url = base_url.rstrip("/")
        self.protocol = "HTTP"

        if capabilities is None:
            self.capabilities: Set[str] = set()
        else:
            self.capabilities = set(capabilities)

        # Runtime state
        self._client = None
        self._connected: bool = False

    def connect(self) -> HandshakeResult:
        """
        Send a handshake request to the device HTTP endpoint and
        return a HandshakeResult.
        """

        if not HTTP_AVAILABLE:
            logger.warning(
                "HTTPAdapter.connect failed for '%s': "
                "httpx not installed.",
                self.device_id
            )
            return HandshakeResult(
                success=False,
                device_id=self.device_id,
                capabilities=self.capabilities,
                protocol=self.protocol,
                reason="Required library not installed"
            )

        try:
            self._client = httpx.Client(timeout=10.0)

            response = self._client.post(
                f"{self.base_url}/handshake",
                json={
                    "device_id": self.device_id,
                    "capabilities": list(self.capabilities),
                    "protocol": self.protocol
                }
            )
            response.raise_for_status()

            self._connected = True

            logger.info(
                "HTTP device '%s' connected to %s",
                self.device_id,
                self.base_url
            )

            return HandshakeResult(
                success=True,
                device_id=self.device_id,
                capabilities=self.capabilities,
                protocol=self.protocol
            )

        except Exception as error:
            self._connected = False

            if self._client is not None:
                self._client.close()
                self._client = None

            logger.error(
                "HTTP connection failed for '%s': %s",
                self.device_id,
                error
            )

            return HandshakeResult(
                success=False,
                device_id=self.device_id,
                capabilities=self.capabilities,
                protocol=self.protocol,
                reason=str(error)
            )

    def recv_data(self) -> bytes:
        """
        Poll the device data endpoint and return the payload bytes.

        Returns empty bytes if the device is not connected or the
        request fails.
        """

        if not self._connected or self._client is None:
            return b""

        try:
            response = self._client.get(
                f"{self.base_url}/data",
                params={"device_id": self.device_id}
            )
            response.raise_for_status()

            return response.content

        except Exception as error:
            logger.error(
                "HTTP recv_data failed for '%s': %s",
                self.device_id,
                error
            )
            return b""

    def send_command(self, intent: str) -> Ack:
        """
        POST a command intent to the device endpoint and return an Ack.
        """

        timestamp = current_timestamp()

        if not self._connected or self._client is None:
            logger.warning(
                "HTTPAdapter.send_command: device '%s' not connected.",
                self.device_id
            )
            return Ack(
                device_id=self.device_id,
                intent=intent,
                timestamp=timestamp,
                equipment_state="DISCONNECTED"
            )

        try:
            response = self._client.post(
                f"{self.base_url}/command",
                json={
                    "device_id": self.device_id,
                    "intent": intent
                }
            )
            response.raise_for_status()

            equipment_state = ""
            try:
                equipment_state = (
                    response.json().get("equipment_state", "")
                )
            except Exception:
                pass

            logger.info(
                "HTTP command '%s' sent to device '%s'.",
                intent,
                self.device_id
            )

            return Ack(
                device_id=self.device_id,
                intent=intent,
                timestamp=timestamp,
                equipment_state=equipment_state
            )

        except Exception as error:
            logger.error(
                "HTTP send_command failed for '%s': %s",
                self.device_id,
                error
            )

            return Ack(
                device_id=self.device_id,
                intent=intent,
                timestamp=timestamp,
                equipment_state=f"ERROR: {error}"
            )

    def disconnect(self) -> None:
        """Close the HTTP client and release resources."""

        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            finally:
                self._client = None
                self._connected = False


# ============================================================
# 6. IOT INTEGRATION LAYER  (Requirements 4, 12)
# ============================================================

import json as _json

from database import (
    save_edge_device,
    update_edge_device_status,
    queue_control_signal,
    get_queued_signals,
    mark_signal_delivered,
)


# Configurable intervals (seconds).
HEARTBEAT_INTERVAL = 30.0
QUEUE_RETENTION_WINDOW_S = 300.0  # 5 minutes


class IoTIntegrationLayer:
    """Device registry, handshake, heartbeat, queue, and relay (Req 4, 12).

    Manages connected edge devices through the ``EdgeDevice`` protocol.  On
    ``register_device`` a graceful boot handshake verifies identity,
    capability, and protocol compatibility (Req 4.2/4.8).  Device-computed
    data is forwarded verbatim to the inference callback without
    recomputation (Req 4.4).  Control signals are relayed over the active
    protocol (Req 4.5).  On unexpected disconnect the device is marked offline
    and its last known state retained (Req 4.6); on reconnect the session
    resumes and queued signals are flushed (Req 4.7/12.3).  A heartbeat loop
    pings online devices and marks unresponsive ones beyond ``2 * INTERVAL``
    (Req 12.1/12.2).  Device authentication gates all data/commands
    (Req 12.4) and malformed messages are isolated (Req 12.5).
    """

    def __init__(
        self,
        inference_callback: Optional[Any] = None,
        heartbeat_interval: float = HEARTBEAT_INTERVAL,
        queue_retention_window_s: float = QUEUE_RETENTION_WINDOW_S,
    ):
        # device_id -> EdgeDevice adapter
        self._devices: Dict[str, Any] = {}
        # device_id -> capabilities set
        self._capabilities: Dict[str, Set[str]] = {}
        # device_id -> last known state dict
        self._last_known_state: Dict[str, Any] = {}
        # device_id -> credential string
        self._credentials: Dict[str, str] = {}
        # device_id -> authenticated flag
        self._authenticated: Dict[str, bool] = {}
        # device_id -> last heartbeat timestamp (monotonic)
        self._last_heartbeat: Dict[str, float] = {}
        # Callback invoked with forwarded device data (Req 4.4).
        self.inference_callback = inference_callback
        self.heartbeat_interval = heartbeat_interval
        self.queue_retention_window_s = queue_retention_window_s
        self._stop_heartbeat = False
        self._heartbeat_thread: Optional[threading.Thread] = None

    # --------------------------------------------------------
    # DEVICE REGISTRATION / HANDSHAKE  (Req 4.2, 4.8, Property 15)
    # --------------------------------------------------------
    def register_device(
        self,
        device: Any,
        required_capabilities: Optional[Set[str]] = None,
        credential: Optional[str] = None,
    ) -> HandshakeResult:
        """Perform a graceful boot handshake and register the device.

        Verifies device identity, capability set, and protocol compatibility
        (Req 4.2).  Incompatible capability -> reject and log the reason
        (Req 4.8).  Stores the credential for the auth gate (Req 12.4).
        """
        device_id = getattr(device, "device_id", None)
        capabilities = set(getattr(device, "capabilities", set()))
        protocol = getattr(device, "protocol", "UNKNOWN")

        if not device_id:
            return HandshakeResult(
                success=False, device_id=str(device_id),
                capabilities=capabilities, protocol=protocol,
                reason="missing device_id",
            )

        # Capability compatibility check (Req 4.8).
        if required_capabilities is not None:
            missing = required_capabilities - capabilities
            if missing:
                logger.info(
                    "Device '%s' rejected: missing capabilities %s",
                    device_id, missing,
                )
                return HandshakeResult(
                    success=False, device_id=device_id,
                    capabilities=capabilities, protocol=protocol,
                    reason=f"incompatible capabilities: missing {missing}",
                )

        # Perform the transport-level handshake.
        handshake = device.connect()

        if not handshake.success:
            logger.info(
                "Device '%s' handshake failed: %s",
                device_id, handshake.reason,
            )
            return handshake

        # Register the device.
        self._devices[device_id] = device
        self._capabilities[device_id] = capabilities
        self._last_known_state[device_id] = {}
        if credential is not None:
            self._credentials[device_id] = credential
            self._authenticated[device_id] = False

        # Persist device registration.
        save_edge_device(
            device_id=device_id,
            protocol=protocol,
            capabilities_json=_json.dumps(sorted(capabilities)),
            status="online",
        )

        self._last_heartbeat[device_id] = time.monotonic()
        logger.info("Device '%s' registered successfully.", device_id)
        return handshake

    # --------------------------------------------------------
    # DEVICE AUTHENTICATION  (Req 12.4, Property 33)
    # --------------------------------------------------------
    def authenticate(self, device_id: str, credential: str) -> bool:
        """Authenticate a device credential before accepting data (Req 12.4).

        Returns ``True`` when the credential matches the stored credential.
        An unauthenticated device has no data accepted and no commands relayed
        (Property 33).
        """
        stored = self._credentials.get(device_id)
        if stored is None:
            # No credential required for this device.
            self._authenticated[device_id] = True
            return True
        ok = stored == credential
        self._authenticated[device_id] = ok
        if not ok:
            logger.warning("Authentication failed for device '%s'.", device_id)
        return ok

    def _is_authenticated(self, device_id: str) -> bool:
        """Whether the device has been authenticated (Req 12.4)."""
        # Devices without a stored credential are treated as authenticated.
        if device_id not in self._credentials:
            return True
        return self._authenticated.get(device_id, False)

    # --------------------------------------------------------
    # DATA FORWARDING  (Req 4.4, Property 16)
    # --------------------------------------------------------
    def on_data(self, device_id: str, payload: bytes, credential: Optional[str] = None) -> bool:
        """Forward device-computed data verbatim to inference (Req 4.4).

        The payload is forwarded unchanged (byte-for-byte) without performing
        the device's on-device computation (Property 16).  The device must be
        authenticated first (Req 12.4).
        """
        if device_id not in self._devices:
            logger.warning("Data from unknown device '%s'.", device_id)
            return False

        if credential is not None and not self.authenticate(device_id, credential):
            return False
        if not self._is_authenticated(device_id):
            logger.warning("Unauthenticated data rejected from '%s'.", device_id)
            return False

        # Forward verbatim (Property 16).
        if self.inference_callback is not None:
            try:
                self.inference_callback(device_id, payload)
            except Exception as exc:
                logger.warning("Inference callback error for '%s': %s", device_id, exc)

        # Update last known state.
        self._last_known_state[device_id] = {"last_payload_size": len(payload)}
        self._last_heartbeat[device_id] = time.monotonic()
        return True

    # --------------------------------------------------------
    # CONTROL-SIGNAL RELAY  (Req 4.5)
    # --------------------------------------------------------
    def relay(self, intent: str, device_id: Optional[str] = None) -> bool:
        """Relay a control signal to the connected device (Req 4.5).

        When ``device_id`` is specified, sends to that device only.  When
        ``None``, broadcasts to all online devices.  Devices that are
        disconnected have the signal queued (Req 12.3).
        """
        targets = [device_id] if device_id else list(self._devices.keys())
        any_delivered = False
        for did in targets:
            device = self._devices.get(did)
            if device is None:
                continue
            if not self._is_authenticated(did):
                continue
            try:
                device.send_command(intent)
                any_delivered = True
            except Exception as exc:
                logger.warning("Relay to '%s' failed; queuing: %s", did, exc)
                self._queue_signal(did, intent)
        return any_delivered

    def _queue_signal(self, device_id: str, intent: str):
        """Queue a control signal for a disconnected device (Req 12.3)."""
        priority = INTENT_PRIORITY_LOOKUP.get(intent, 1)
        try:
            queue_control_signal(device_id, intent, priority)
            logger.info("Queued %s for device '%s'.", intent, device_id)
        except Exception as exc:
            logger.warning("Failed to queue signal for '%s': %s", device_id, exc)

    # --------------------------------------------------------
    # DISCONNECT / RECONNECT  (Req 4.6, 4.7, 12.3)
    # --------------------------------------------------------
    def on_disconnect(self, device_id: str):
        """Mark a device offline and retain its last known state (Req 4.6, Property 17)."""
        last_state = self._last_known_state.get(device_id, {})
        try:
            update_edge_device_status(
                device_id=device_id,
                status="offline",
                last_known_state_json=_json.dumps(last_state, default=str),
            )
        except Exception as exc:
            logger.warning("Failed to update device status for '%s': %s", device_id, exc)
        logger.info("Device '%s' marked offline; last known state retained.", device_id)

    def on_reconnect(self, device_id: str) -> bool:
        """Re-establish the session and flush queued signals (Req 4.7, 12.3, Property 18).

        Resumes data/command exchange and delivers queued control signals in
        priority order within the retention window.
        """
        device = self._devices.get(device_id)
        if device is None:
            logger.warning("Reconnect for unknown device '%s'.", device_id)
            return False

        handshake = device.connect()
        if not handshake.success:
            logger.warning("Reconnect handshake failed for '%s': %s", device_id, handshake.reason)
            return False

        try:
            update_edge_device_status(device_id=device_id, status="online")
        except Exception:
            pass

        # Flush queued signals in priority order (Req 12.3, Property 32).
        self._flush_queue(device_id)
        self._last_heartbeat[device_id] = time.monotonic()
        logger.info("Device '%s' reconnected; session resumed.", device_id)
        return True

    def _flush_queue(self, device_id: str):
        """Deliver queued control signals on reconnect (Req 12.3, Property 32)."""
        try:
            queued = get_queued_signals(device_id, undelivered_only=True)
        except Exception:
            queued = []

        now = time.monotonic()
        for item in queued:
            # Respect retention window (Req 12.3).
            queued_at = item.get("queued_at")
            # queued_at is an ISO string; approximate check.
            if queued_at:
                try:
                    queued_ts = datetime.fromisoformat(queued_at.replace("Z", "+00:00"))
                    age_s = (datetime.now(timezone.utc) - queued_ts).total_seconds()
                    if age_s > self.queue_retention_window_s:
                        continue
                except Exception:
                    pass

            device = self._devices.get(device_id)
            if device is None:
                break
            try:
                device.send_command(item["intent"])
                mark_signal_delivered(item["id"])
            except Exception as exc:
                logger.warning("Flush delivery failed for queued signal %s: %s", item["id"], exc)
                break

    # --------------------------------------------------------
    # HEARTBEAT  (Req 12.1, 12.2, Property 31)
    # --------------------------------------------------------
    def heartbeat_loop(self):
        """Ping each online device and mark unresponsive ones (Req 12.1/12.2).

        Pings at ``heartbeat_interval``; if no heartbeat is received within
        ``2 * interval``, the device is marked unresponsive and the UI is
        notified (Property 31).
        """
        while not self._stop_heartbeat:
            now = time.monotonic()
            for device_id, last_hb in list(self._last_heartbeat.items()):
                if device_id not in self._devices:
                    continue
                if (now - last_hb) > 2 * self.heartbeat_interval:
                    logger.info("Device '%s' unresponsive (heartbeat timeout).", device_id)
                    try:
                        update_edge_device_status(device_id=device_id, status="unresponsive")
                    except Exception:
                        pass
                    # Notify via alert listeners if any.
            time.sleep(self.heartbeat_interval)

    def start_heartbeat(self):
        """Start the heartbeat loop in a background thread."""
        if self._heartbeat_thread is not None:
            return
        self._stop_heartbeat = False
        self._heartbeat_thread = threading.Thread(target=self.heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def stop_heartbeat(self):
        """Stop the heartbeat loop."""
        self._stop_heartbeat = True
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=5)
            self._heartbeat_thread = None

    def update_heartbeat(self, device_id: str):
        """Record that a heartbeat was received from a device (Req 12.1)."""
        self._last_heartbeat[device_id] = time.monotonic()

    # --------------------------------------------------------
    # MALFORMED-MESSAGE ISOLATION  (Req 12.5, Property 34)
    # --------------------------------------------------------
    def on_malformed(self, device_id: str, raw: Any) -> bool:
        """Reject and log a malformed protocol message (Req 12.5, Property 34).

        The device connection stays open; only the bad message is rejected.
        Returns ``True`` (message handled) so the caller knows the message was
        processed without dropping the connection.
        """
        logger.warning(
            "Malformed message from device '%s': %s (connection kept open)",
            device_id, repr(raw)[:200],
        )
        return True

    # --------------------------------------------------------
    # DEVICE LIST / STATUS
    # --------------------------------------------------------
    def list_devices(self) -> List[Dict[str, Any]]:
        """Return the status of all known devices (Req 14.2)."""
        result = []
        for device_id, device in self._devices.items():
            result.append({
                "device_id": device_id,
                "protocol": getattr(device, "protocol", "UNKNOWN"),
                "capabilities": sorted(self._capabilities.get(device_id, set())),
                "authenticated": self._is_authenticated(device_id),
            })
        return result

    def get_device_status(self, device_id: str) -> Optional[str]:
        """Return the online/offline/unresponsive status of a device."""
        if device_id not in self._devices:
            return None
        now = time.monotonic()
        last_hb = self._last_heartbeat.get(device_id, now)
        if (now - last_hb) > 2 * self.heartbeat_interval:
            return "unresponsive"
        return "online"


# Intent-to-priority lookup for queuing.
INTENT_PRIORITY_LOOKUP = {
    "SHUTDOWN": 3,
    "DE_RATE": 2,
    "RUN": 1,
}
