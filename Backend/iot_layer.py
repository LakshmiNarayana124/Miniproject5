
"""
IntelliWatch - IoT Integration Layer

Responsibilities:
1. Define the EdgeDevice protocol abstraction.
2. Provide HandshakeResult and Ack data structures.
3. Implement MQTT and HTTP protocol adapters.
4. Manage device registration, credentials, heartbeat, data ingestion,
   control-signal delivery, and malformed-message handling.
5. Keep validated hardware readings available to the server.
6. Gracefully degrade when transport libraries are unavailable.

Transport payload contract for MQTT and HTTP polling:

{
    "credential": "<device credential>",
    "readings": {
        "vibration": {
            "value": 0.2,
            "unit": "g",
            "quality": "GOOD",
            "metadata": {}
        },
        "temperature": {
            "value": 32.0,
            "unit": "°C",
            "quality": "GOOD"
        },
        "current": {
            "value": 1.8,
            "unit": "A",
            "quality": "GOOD"
        }
    }
}

For direct HTTP push ingestion, the credential is supplied separately
through the X-Device-Credential request header.
"""

import hmac
import json
import logging
import math
import secrets
import threading
import time

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Protocol, Set, Dict, List, Any, Callable

from database import (
    current_timestamp,
    save_edge_device,
    update_edge_device_status,
    queue_control_signal,
    get_queued_signals,
    mark_signal_delivered,
)


logger = logging.getLogger(__name__)


__all__ = [
    "EdgeDevice",
    "HandshakeResult",
    "Ack",
    "MQTTAdapter",
    "HTTPAdapter",
    "IoTIntegrationLayer",
    "MQTT_AVAILABLE",
    "HTTP_AVAILABLE",
]


# ============================================================
# 1. CONFIGURATION
# ============================================================

HEARTBEAT_INTERVAL = 30.0
QUEUE_RETENTION_WINDOW_S = 300.0
MAX_SENSOR_PAYLOAD_BYTES = 64 * 1024
HTTP_POLL_INTERVAL = 1.0

VALID_SENSOR_KEYS = {
    "vibration",
    "temperature",
    "current",
}

VALID_QUALITY_VALUES = {
    "GOOD",
    "VALID",
    "WARNING",
    "DEGRADED",
    "ERROR",
    "UNAVAILABLE",
}

INTENT_PRIORITY_LOOKUP = {
    "SHUTDOWN": 3,
    "DE_RATE": 2,
    "RUN": 1,
}


# ============================================================
# 2. TRANSPORT LIBRARY IMPORTS
# ============================================================

try:
    import paho.mqtt.client as mqtt

    MQTT_AVAILABLE = True

except ImportError:
    mqtt = None
    MQTT_AVAILABLE = False

    logger.warning(
        "paho-mqtt is not installed. "
        "MQTTAdapter will not be functional."
    )


try:
    import httpx

    HTTP_AVAILABLE = True

except ImportError:
    httpx = None
    HTTP_AVAILABLE = False

    logger.warning(
        "httpx is not installed. "
        "HTTPAdapter will not be functional."
    )


# ============================================================
# 3. DATA STRUCTURES
# ============================================================

@dataclass
class HandshakeResult:
    """
    Outcome of a device boot handshake.

    device_credential is returned once during successful registration.
    It must be securely configured on the edge device.
    """

    success: bool
    device_id: str
    capabilities: Set[str]
    protocol: str
    reason: str = ""

    # Do not expose credentials in logs or object representations.
    device_credential: Optional[str] = field(
        default=None,
        repr=False,
    )


@dataclass
class Ack:
    """Acknowledgement returned after a control command."""

    device_id: str
    intent: str
    timestamp: str
    equipment_state: str = ""


# ============================================================
# 4. EDGE DEVICE PROTOCOL
# ============================================================

class EdgeDevice(Protocol):
    """Common interface for supported edge-device adapters."""

    device_id: str
    capabilities: Set[str]
    protocol: str

    def connect(self) -> HandshakeResult:
        ...

    def recv_data(self) -> bytes:
        ...

    def send_command(self, intent: str) -> Ack:
        ...


# ============================================================
# 5. MQTT ADAPTER
# ============================================================

class MQTTAdapter:
    """
    MQTT transport adapter.

    MQTT messages use an authenticated envelope containing:
        credential
        readings

    The integration layer validates the credential and sensor payload.
    """

    def __init__(
        self,
        device_id: str,
        broker_host: str,
        broker_port: int = 1883,
        capabilities: Optional[Set[str]] = None,
    ):
        self.device_id = device_id
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.protocol = "MQTT"

        self.capabilities = set(capabilities or set())

        self._data_topic = (
            f"intelliwatch/devices/{device_id}/data"
        )
        self._command_topic = (
            f"intelliwatch/devices/{device_id}/command"
        )

        self._client = None
        self._latest_payload = b""
        self._connected = False

        self._message_handler: Optional[
            Callable[[bytes], None]
        ] = None

        self._payload_lock = threading.Lock()

    def set_message_handler(self, handler):
        """Set the callback used for incoming MQTT messages."""

        self._message_handler = handler

    def _on_message(self, client, userdata, message):
        payload = message.payload or b""

        with self._payload_lock:
            self._latest_payload = payload

        handler = self._message_handler

        if handler is not None:
            try:
                handler(payload)
            except Exception:
                logger.exception(
                    "MQTT message handler failed for '%s'.",
                    self.device_id,
                )

    def connect(self) -> HandshakeResult:
        if not MQTT_AVAILABLE:
            return HandshakeResult(
                False,
                self.device_id,
                self.capabilities,
                self.protocol,
                "Required library not installed",
            )

        try:
            self._client = mqtt.Client(
                client_id=f"intelliwatch-{self.device_id}"
            )

            self._client.on_message = self._on_message

            self._client.connect(
                self.broker_host,
                self.broker_port,
                keepalive=60,
            )

            self._client.subscribe(self._data_topic)
            self._client.loop_start()

            self._connected = True

            logger.info(
                "MQTT transport connected for device '%s'.",
                self.device_id,
            )

            return HandshakeResult(
                True,
                self.device_id,
                set(self.capabilities),
                self.protocol,
            )

        except Exception as error:
            self.disconnect()

            logger.error(
                "MQTT connection failed for '%s': %s",
                self.device_id,
                error,
            )

            return HandshakeResult(
                False,
                self.device_id,
                self.capabilities,
                self.protocol,
                str(error),
            )

    def recv_data(self) -> bytes:
        if not self._connected or self._client is None:
            return b""

        with self._payload_lock:
            return self._latest_payload

    def send_command(self, intent: str) -> Ack:
        timestamp = current_timestamp()

        if not self._connected or self._client is None:
            return Ack(
                self.device_id,
                intent,
                timestamp,
                "DISCONNECTED",
            )

        try:
            result = self._client.publish(
                self._command_topic,
                intent,
            )

            if getattr(result, "rc", 0) != 0:
                return Ack(
                    self.device_id,
                    intent,
                    timestamp,
                    "ERROR: MQTT publish failed",
                )

            return Ack(
                self.device_id,
                intent,
                timestamp,
                "SENT",
            )

        except Exception as error:
            logger.error(
                "MQTT command failed for '%s': %s",
                self.device_id,
                error,
            )

            return Ack(
                self.device_id,
                intent,
                timestamp,
                f"ERROR: {error}",
            )

    def disconnect(self):
        if self._client is not None:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass

        self._client = None
        self._connected = False


# ============================================================
# 6. HTTP ADAPTER
# ============================================================

class HTTPAdapter:
    """
    HTTP transport adapter.

    Requests to the edge device include its registered credential.
    The device's /data response must use the authenticated envelope
    documented at the top of this file.
    """

    def __init__(
        self,
        device_id: str,
        base_url: str,
        capabilities: Optional[Set[str]] = None,
    ):
        self.device_id = device_id
        self.base_url = base_url.rstrip("/")
        self.protocol = "HTTP"

        self.capabilities = set(capabilities or set())

        self._client = None
        self._connected = False
        self._credential: Optional[str] = None

    def set_device_credential(self, credential: str):
        self._credential = credential

    def _headers(self):
        if not self._credential:
            return {}

        return {
            "X-Device-Credential": self._credential,
        }

    def connect(self) -> HandshakeResult:
        if not HTTP_AVAILABLE:
            return HandshakeResult(
                False,
                self.device_id,
                self.capabilities,
                self.protocol,
                "Required library not installed",
            )

        try:
            self._client = httpx.Client(timeout=10.0)

            response = self._client.post(
                f"{self.base_url}/handshake",
                json={
                    "device_id": self.device_id,
                    "capabilities": sorted(self.capabilities),
                    "protocol": self.protocol,
                },
                headers=self._headers(),
            )

            response.raise_for_status()

            # Verify device identity when the device reports it.
            try:
                response_data = response.json()
            except Exception:
                response_data = {}

            reported_id = response_data.get("device_id")

            if reported_id and reported_id != self.device_id:
                raise ValueError(
                    "Handshake device identity mismatch"
                )

            self._connected = True

            logger.info(
                "HTTP transport connected for device '%s'.",
                self.device_id,
            )

            return HandshakeResult(
                True,
                self.device_id,
                set(self.capabilities),
                self.protocol,
            )

        except Exception as error:
            self.disconnect()

            logger.error(
                "HTTP connection failed for '%s': %s",
                self.device_id,
                error,
            )

            return HandshakeResult(
                False,
                self.device_id,
                self.capabilities,
                self.protocol,
                str(error),
            )

    def recv_data(self) -> bytes:
        if not self._connected or self._client is None:
            return b""

        try:
            response = self._client.get(
                f"{self.base_url}/data",
                params={"device_id": self.device_id},
                headers=self._headers(),
            )

            response.raise_for_status()
            return response.content

        except Exception as error:
            logger.warning(
                "HTTP data polling failed for '%s': %s",
                self.device_id,
                error,
            )

            return b""

    def send_command(self, intent: str) -> Ack:
        timestamp = current_timestamp()

        if not self._connected or self._client is None:
            return Ack(
                self.device_id,
                intent,
                timestamp,
                "DISCONNECTED",
            )

        try:
            response = self._client.post(
                f"{self.base_url}/command",
                json={
                    "device_id": self.device_id,
                    "intent": intent,
                },
                headers=self._headers(),
            )

            response.raise_for_status()

            equipment_state = "SENT"

            try:
                data = response.json()
                equipment_state = data.get(
                    "equipment_state",
                    "SENT",
                )
            except Exception:
                pass

            return Ack(
                self.device_id,
                intent,
                timestamp,
                equipment_state,
            )

        except Exception as error:
            logger.error(
                "HTTP command failed for '%s': %s",
                self.device_id,
                error,
            )

            return Ack(
                self.device_id,
                intent,
                timestamp,
                f"ERROR: {error}",
            )

    def disconnect(self):
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass

        self._client = None
        self._connected = False


# ============================================================
# 7. IOT INTEGRATION LAYER
# ============================================================

class IoTIntegrationLayer:
    """
    Manages authenticated edge devices and hardware sensor ingestion.

    Supported ingestion routes:
      1. Direct HTTP push through on_data().
      2. MQTT subscription through MQTTAdapter callbacks.
      3. HTTP polling through HTTPAdapter.

    Sensor data is validated before it is exposed as a hardware snapshot.

    The inference callback retains the existing signature:
        callback(device_id, raw_payload_bytes)
    """

    def __init__(
        self,
        inference_callback: Optional[Any] = None,
        heartbeat_interval: float = HEARTBEAT_INTERVAL,
        queue_retention_window_s: float = QUEUE_RETENTION_WINDOW_S,
        http_poll_interval: float = HTTP_POLL_INTERVAL,
    ):
        self._devices: Dict[str, Any] = {}
        self._capabilities: Dict[str, Set[str]] = {}
        self._credentials: Dict[str, str] = {}
        self._authenticated: Dict[str, bool] = {}

        self._last_known_state: Dict[str, Any] = {}
        self._last_heartbeat: Dict[str, float] = {}
        self._latest_readings: Dict[str, Dict[str, Any]] = {}

        self._unresponsive_devices: Set[str] = set()

        self._poll_threads: Dict[str, threading.Thread] = {}
        self._poll_stop_events: Dict[str, threading.Event] = {}

        self.inference_callback = inference_callback

        self.heartbeat_interval = max(
            1.0,
            float(heartbeat_interval),
        )

        self.queue_retention_window_s = max(
            0.0,
            float(queue_retention_window_s),
        )

        self.http_poll_interval = max(
            0.25,
            float(http_poll_interval),
        )

        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._heartbeat_thread: Optional[
            threading.Thread
        ] = None

    # --------------------------------------------------------
    # CREDENTIALS
    # --------------------------------------------------------

    @staticmethod
    def _generate_credential() -> str:
        """Generate a cryptographically strong device credential."""

        return secrets.token_urlsafe(32)

    def authenticate(
        self,
        device_id: str,
        credential: Optional[str],
    ) -> bool:
        """Verify a registered device credential using constant-time comparison."""

        if not isinstance(credential, str) or not credential:
            return False

        with self._lock:
            stored = self._credentials.get(device_id)

            if stored is None:
                return False

            authenticated = hmac.compare_digest(
                stored,
                credential,
            )

            self._authenticated[device_id] = authenticated

        if not authenticated:
            logger.warning(
                "Authentication failed for device '%s'.",
                device_id,
            )

        return authenticated

    def _is_authenticated(self, device_id: str) -> bool:
        with self._lock:
            return (
                device_id in self._credentials
                and self._authenticated.get(device_id, False)
            )

    # --------------------------------------------------------
    # DEVICE REGISTRATION
    # --------------------------------------------------------

    def register_device(
        self,
        device: Any,
        required_capabilities: Optional[Set[str]] = None,
        credential: Optional[str] = None,
    ) -> HandshakeResult:
        """
        Connect and register an edge device.

        When no credential is supplied, a secure credential is generated.
        The successful HandshakeResult returns it once to the caller.
        """

        device_id = getattr(device, "device_id", None)
        capabilities = set(
            getattr(device, "capabilities", set())
        )
        protocol = str(
            getattr(device, "protocol", "UNKNOWN")
        ).upper()

        if (
            not isinstance(device_id, str)
            or not device_id.strip()
            or len(device_id) > 128
        ):
            return HandshakeResult(
                False,
                str(device_id),
                capabilities,
                protocol,
                "Invalid device_id",
            )

        device_id = device_id.strip()

        if protocol not in {"HTTP", "MQTT"}:
            return HandshakeResult(
                False,
                device_id,
                capabilities,
                protocol,
                "Unsupported device protocol",
            )

        if required_capabilities is not None:
            missing = set(required_capabilities) - capabilities

            if missing:
                return HandshakeResult(
                    False,
                    device_id,
                    capabilities,
                    protocol,
                    f"Missing capabilities: {sorted(missing)}",
                )

        with self._lock:
            if device_id in self._devices:
                return HandshakeResult(
                    False,
                    device_id,
                    capabilities,
                    protocol,
                    "Device is already registered",
                )

        device_credential = (
            credential
            if credential is not None
            else self._generate_credential()
        )

        if (
            not isinstance(device_credential, str)
            or len(device_credential) < 32
        ):
            return HandshakeResult(
                False,
                device_id,
                capabilities,
                protocol,
                "Device credential must contain at least 32 characters",
            )

        # Configure adapter authentication before connecting.
        if hasattr(device, "set_device_credential"):
            device.set_device_credential(device_credential)

        if hasattr(device, "set_message_handler"):
            device.set_message_handler(
                lambda raw, did=device_id:
                    self._handle_transport_envelope(did, raw)
            )

        try:
            handshake = device.connect()
        except Exception as error:
            logger.exception(
                "Device handshake raised an exception for '%s'.",
                device_id,
            )

            return HandshakeResult(
                False,
                device_id,
                capabilities,
                protocol,
                str(error),
            )

        if not handshake.success:
            return handshake

        if handshake.device_id != device_id:
            try:
                device.disconnect()
            except Exception:
                pass

            return HandshakeResult(
                False,
                device_id,
                capabilities,
                protocol,
                "Handshake device identity mismatch",
            )

        with self._lock:
            self._devices[device_id] = device
            self._capabilities[device_id] = capabilities
            self._credentials[device_id] = device_credential

            # Registration alone does not authenticate incoming data.
            self._authenticated[device_id] = False

            self._last_known_state[device_id] = {}
            self._last_heartbeat[device_id] = time.monotonic()

            self._unresponsive_devices.discard(device_id)

        try:
            save_edge_device(
                device_id=device_id,
                protocol=protocol,
                capabilities_json=json.dumps(
                    sorted(capabilities)
                ),
                status="online",
            )
        except Exception:
            logger.exception(
                "Device '%s' registered in memory, but database "
                "registration could not be saved.",
                device_id,
            )

        if protocol == "HTTP":
            self._start_http_poller(device_id)

        logger.info(
            "Device '%s' registered successfully using %s.",
            device_id,
            protocol,
        )

        return HandshakeResult(
            success=True,
            device_id=device_id,
            capabilities=capabilities,
            protocol=protocol,
            device_credential=device_credential,
        )

    # --------------------------------------------------------
    # SENSOR PAYLOAD VALIDATION
    # --------------------------------------------------------

    @staticmethod
    def _contains_simulation_source(value: Any) -> bool:
        """Detect explicit simulation-source declarations in the payload."""

        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() in {
                    "source",
                    "data_source",
                }:
                    if str(child).strip().lower() in {
                        "simulation",
                        "simulated",
                        "offline-demo",
                        "demo",
                    }:
                        return True

                if IoTIntegrationLayer._contains_simulation_source(
                    child
                ):
                    return True

        elif isinstance(value, list):
            return any(
                IoTIntegrationLayer._contains_simulation_source(item)
                for item in value
            )

        return False

    @staticmethod
    def _validate_sensor_payload(
        raw_payload: bytes,
    ) -> Optional[Dict[str, Any]]:
        """
        Validate a JSON sensor snapshot.

        Unknown units are retained rather than silently converted.
        At least one recognised sensor record must be present.
        """

        if not isinstance(raw_payload, bytes):
            return None

        if not raw_payload or len(raw_payload) > MAX_SENSOR_PAYLOAD_BYTES:
            return None

        try:
            payload = json.loads(raw_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

        if not isinstance(payload, dict):
            return None

        if IoTIntegrationLayer._contains_simulation_source(payload):
            logger.warning(
                "Rejected payload containing an explicit simulation source."
            )
            return None

        readings = payload.get("readings", payload)

        if not isinstance(readings, dict):
            return None

        validated: Dict[str, Any] = {}

        for sensor_key in VALID_SENSOR_KEYS:
            if sensor_key not in readings:
                continue

            record = readings[sensor_key]

            if not isinstance(record, dict):
                return None

            if "value" not in record:
                return None

            value = record.get("value")
            unit = record.get("unit")
            quality = str(
                record.get("quality", "")
            ).upper()

            if (
                not isinstance(unit, str)
                or not unit.strip()
            ):
                return None

            if quality not in VALID_QUALITY_VALUES:
                return None

            if value is None:
                if quality not in {"ERROR", "UNAVAILABLE"}:
                    return None

            else:
                if isinstance(value, bool):
                    return None

                if not isinstance(value, (int, float)):
                    return None

                if not math.isfinite(float(value)):
                    return None

            metadata = record.get("metadata", {})

            if not isinstance(metadata, dict):
                return None

            clean_record = deepcopy(record)
            clean_metadata = deepcopy(metadata)

            # The server, not the device, determines the source label.
            clean_metadata["source"] = "hardware"

            clean_record["quality"] = quality
            clean_record["metadata"] = clean_metadata
            clean_record["source"] = "hardware"

            validated[sensor_key] = clean_record

        if not validated:
            return None

        received_at = time.time()

        return {
            "timestamp": received_at,
            "device_timestamp": payload.get(
                "timestamp",
                payload.get("ts"),
            ),
            "device_id": None,
            "source": "hardware",
            **validated,
        }

    # --------------------------------------------------------
    # MQTT / HTTP TRANSPORT ENVELOPE
    # --------------------------------------------------------

    def _handle_transport_envelope(
        self,
        device_id: str,
        raw_payload: bytes,
    ) -> bool:
        """
        Validate the transport envelope and forward its readings.

        MQTT and HTTP polling require:
            {
                "credential": "...",
                "readings": {...}
            }
        """

        try:
            if not isinstance(raw_payload, bytes):
                return self.on_malformed(
                    device_id,
                    raw_payload,
                )

            envelope = json.loads(
                raw_payload.decode("utf-8")
            )

            if not isinstance(envelope, dict):
                return self.on_malformed(
                    device_id,
                    raw_payload,
                )

            credential = envelope.get("credential")
            readings = envelope.get("readings")

            if not isinstance(readings, dict):
                return self.on_malformed(
                    device_id,
                    raw_payload,
                )

            clean_payload = json.dumps(
                readings,
                allow_nan=False,
            ).encode("utf-8")

            return self.on_data(
                device_id,
                clean_payload,
                credential=credential,
            )

        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            return self.on_malformed(
                device_id,
                raw_payload,
            )

        except Exception:
            logger.exception(
                "Transport envelope handling failed for '%s'.",
                device_id,
            )
            return False

    # --------------------------------------------------------
    # DATA INGESTION
    # --------------------------------------------------------

    def on_data(
        self,
        device_id: str,
        payload: bytes,
        credential: Optional[str] = None,
    ) -> bool:
        """
        Authenticate, validate, and accept a device sensor payload.

        The original payload bytes are forwarded to the inference callback.
        A validated hardware snapshot is retained for the server/dashboard.
        """

        with self._lock:
            if device_id not in self._devices:
                logger.warning(
                    "Data received from unknown device '%s'.",
                    device_id,
                )
                return False

        if not self.authenticate(device_id, credential):
            return False

        validated = self._validate_sensor_payload(payload)

        if validated is None:
            self.on_malformed(device_id, payload)
            return False

        validated["device_id"] = device_id

        # Forward the original device-computed bytes to the callback.
        if self.inference_callback is not None:
            try:
                self.inference_callback(
                    device_id,
                    payload,
                )
            except Exception:
                logger.exception(
                    "Inference callback failed for '%s'.",
                    device_id,
                )
                return False

        with self._lock:
            self._latest_readings[device_id] = deepcopy(
                validated
            )

            self._last_known_state[device_id] = deepcopy(
                validated
            )

            self._last_heartbeat[device_id] = time.monotonic()

            self._authenticated[device_id] = True
            self._unresponsive_devices.discard(device_id)

        try:
            update_edge_device_status(
                device_id=device_id,
                status="online",
                last_known_state_json=json.dumps(
                    validated,
                    default=str,
                ),
            )
        except Exception:
            logger.debug(
                "Could not update device status for '%s'.",
                device_id,
            )

        return True

    # --------------------------------------------------------
    # HTTP POLLING
    # --------------------------------------------------------

    def _start_http_poller(self, device_id: str):
        with self._lock:
            existing = self._poll_threads.get(device_id)

            if existing is not None and existing.is_alive():
                return

            stop_event = threading.Event()
            self._poll_stop_events[device_id] = stop_event

            thread = threading.Thread(
                target=self._http_poll_loop,
                args=(device_id, stop_event),
                daemon=True,
                name=f"IntelliWatch-HTTP-{device_id}",
            )

            self._poll_threads[device_id] = thread

        thread.start()

    def _http_poll_loop(
        self,
        device_id: str,
        stop_event: threading.Event,
    ):
        while (
            not stop_event.is_set()
            and not self._stop_event.is_set()
        ):
            with self._lock:
                device = self._devices.get(device_id)

            if device is None:
                break

            try:
                raw_payload = device.recv_data()

                if raw_payload:
                    self._handle_transport_envelope(
                        device_id,
                        raw_payload,
                    )

            except Exception:
                logger.exception(
                    "HTTP polling failed for '%s'.",
                    device_id,
                )

            stop_event.wait(self.http_poll_interval)

    # --------------------------------------------------------
    # LATEST HARDWARE SNAPSHOT
    # --------------------------------------------------------

    def get_latest_sensor_snapshot(
        self,
        device_id: Optional[str] = None,
        max_age_seconds: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Return the newest validated hardware snapshot.

        When device_id is omitted, the most recently updated device
        snapshot is returned.

        max_age_seconds can be supplied by the server to reject stale data.
        """

        with self._lock:
            if device_id is not None:
                snapshot = self._latest_readings.get(device_id)

                if snapshot is None:
                    return None

                result = deepcopy(snapshot)

            else:
                if not self._latest_readings:
                    return None

                result = deepcopy(
                    max(
                        self._latest_readings.values(),
                        key=lambda item: item.get(
                            "timestamp",
                            0,
                        ),
                    )
                )

        received_at = result.get("timestamp", 0)

        if max_age_seconds is not None:
            if time.time() - received_at > max_age_seconds:
                return None

        return result

    # Backwards-friendly alias for server code.
    def get_latest_readings(
        self,
        device_id: Optional[str] = None,
        max_age_seconds: Optional[float] = None,
    ):
        return self.get_latest_sensor_snapshot(
            device_id=device_id,
            max_age_seconds=max_age_seconds,
        )

    # --------------------------------------------------------
    # CONTROL-SIGNAL RELAY
    # --------------------------------------------------------

    @staticmethod
    def _ack_was_delivered(ack: Any) -> bool:
        if ack is None:
            return False

        state = str(
            getattr(ack, "equipment_state", "")
        ).strip().upper()

        return not (
            state == "DISCONNECTED"
            or state.startswith("ERROR")
            or state in {"FAILED", "REJECTED"}
        )

    def relay(
        self,
        intent: str,
        device_id: Optional[str] = None,
    ) -> bool:
        """Relay a control signal only to authenticated devices."""

        intent = str(intent).upper()

        if intent not in INTENT_PRIORITY_LOOKUP:
            logger.warning(
                "Rejected unsupported control intent '%s'.",
                intent,
            )
            return False

        with self._lock:
            targets = (
                [device_id]
                if device_id
                else list(self._devices.keys())
            )

        delivered_any = False

        for target_id in targets:
            with self._lock:
                device = self._devices.get(target_id)

            if device is None:
                continue

            if not self._is_authenticated(target_id):
                logger.warning(
                    "Control relay rejected for unauthenticated device '%s'.",
                    target_id,
                )
                continue

            try:
                ack = device.send_command(intent)

                if self._ack_was_delivered(ack):
                    delivered_any = True
                else:
                    self._queue_signal(
                        target_id,
                        intent,
                    )

            except Exception:
                logger.exception(
                    "Control relay failed for '%s'.",
                    target_id,
                )

                self._queue_signal(
                    target_id,
                    intent,
                )

        return delivered_any

    def _queue_signal(
        self,
        device_id: str,
        intent: str,
    ):
        priority = INTENT_PRIORITY_LOOKUP.get(
            intent,
            1,
        )

        try:
            queue_control_signal(
                device_id,
                intent,
                priority,
            )

            logger.info(
                "Queued %s for device '%s'.",
                intent,
                device_id,
            )

        except Exception:
            logger.exception(
                "Failed to queue signal for '%s'.",
                device_id,
            )

    # --------------------------------------------------------
    # DISCONNECT / RECONNECT
    # --------------------------------------------------------

    def on_disconnect(self, device_id: str):
        """Mark a device offline and preserve its last known state."""

        with self._lock:
            device = self._devices.get(device_id)
            last_state = deepcopy(
                self._last_known_state.get(device_id, {})
            )

            stop_event = self._poll_stop_events.get(device_id)

        if stop_event is not None:
            stop_event.set()

        if device is not None:
            try:
                device.disconnect()
            except Exception:
                logger.debug(
                    "Transport disconnect error for '%s'.",
                    device_id,
                )

        try:
            update_edge_device_status(
                device_id=device_id,
                status="offline",
                last_known_state_json=json.dumps(
                    last_state,
                    default=str,
                ),
            )
        except Exception:
            logger.exception(
                "Could not mark device '%s' offline.",
                device_id,
            )

    def on_reconnect(self, device_id: str) -> bool:
        """Reconnect a registered device and flush eligible queued signals."""

        with self._lock:
            device = self._devices.get(device_id)

        if device is None:
            return False

        try:
            handshake = device.connect()
        except Exception:
            logger.exception(
                "Reconnect failed for '%s'.",
                device_id,
            )
            return False

        if not handshake.success or handshake.device_id != device_id:
            logger.warning(
                "Reconnect handshake rejected for '%s'.",
                device_id,
            )
            return False

        with self._lock:
            self._last_heartbeat[device_id] = time.monotonic()
            self._unresponsive_devices.discard(device_id)

        try:
            update_edge_device_status(
                device_id=device_id,
                status="online",
            )
        except Exception:
            logger.debug(
                "Could not update reconnect status for '%s'.",
                device_id,
            )

        if getattr(device, "protocol", "").upper() == "HTTP":
            self._start_http_poller(device_id)

        if self._is_authenticated(device_id):
            self._flush_queue(device_id)

        return True

    def _flush_queue(self, device_id: str):
        if not self._is_authenticated(device_id):
            return

        try:
            queued = get_queued_signals(
                device_id,
                undelivered_only=True,
            )
        except Exception:
            logger.exception(
                "Could not retrieve queued signals for '%s'.",
                device_id,
            )
            return

        with self._lock:
            device = self._devices.get(device_id)

        if device is None:
            return

        for item in queued:
            queued_at = item.get("queued_at")

            if queued_at:
                try:
                    queued_ts = datetime.fromisoformat(
                        queued_at.replace("Z", "+00:00")
                    )

                    age_seconds = (
                        datetime.now(timezone.utc) - queued_ts
                    ).total_seconds()

                    if age_seconds > self.queue_retention_window_s:
                        logger.info(
                            "Expired queued signal %s for '%s'.",
                            item.get("id"),
                            device_id,
                        )
                        continue

                except (ValueError, TypeError):
                    logger.warning(
                        "Could not verify queue age for signal %s.",
                        item.get("id"),
                    )
                    continue

            try:
                ack = device.send_command(item["intent"])

                if not self._ack_was_delivered(ack):
                    logger.warning(
                        "Queued signal %s was not confirmed by '%s'.",
                        item.get("id"),
                        device_id,
                    )
                    break

                mark_signal_delivered(item["id"])

            except Exception:
                logger.exception(
                    "Queued signal delivery failed for '%s'.",
                    device_id,
                )
                break

    # --------------------------------------------------------
    # HEARTBEAT
    # --------------------------------------------------------

    def heartbeat_loop(self):
        """
        Mark devices unresponsive when no valid data/heartbeat is received
        within twice the configured heartbeat interval.
        """

        while not self._stop_event.wait(self.heartbeat_interval):
            now = time.monotonic()

            with self._lock:
                heartbeat_items = list(
                    self._last_heartbeat.items()
                )

            for device_id, last_heartbeat in heartbeat_items:
                if (
                    now - last_heartbeat
                    <= 2 * self.heartbeat_interval
                ):
                    continue

                with self._lock:
                    if device_id in self._unresponsive_devices:
                        continue

                    self._unresponsive_devices.add(device_id)

                logger.warning(
                    "Device '%s' is unresponsive.",
                    device_id,
                )

                try:
                    update_edge_device_status(
                        device_id=device_id,
                        status="unresponsive",
                    )
                except Exception:
                    logger.exception(
                        "Could not update unresponsive status for '%s'.",
                        device_id,
                    )

    def start_heartbeat(self):
        if (
            self._heartbeat_thread is not None
            and self._heartbeat_thread.is_alive()
        ):
            return

        self._stop_event.clear()

        self._heartbeat_thread = threading.Thread(
            target=self.heartbeat_loop,
            daemon=True,
            name="IntelliWatch-IoT-Heartbeat",
        )

        self._heartbeat_thread.start()

        with self._lock:
            http_devices = [
                device_id
                for device_id, device in self._devices.items()
                if getattr(device, "protocol", "").upper() == "HTTP"
            ]

        for device_id in http_devices:
            self._start_http_poller(device_id)

    def stop_heartbeat(self):
        self._stop_event.set()

        with self._lock:
            poll_events = list(
                self._poll_stop_events.values()
            )

            poll_threads = list(
                self._poll_threads.values()
            )

        for event in poll_events:
            event.set()

        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=5)
            self._heartbeat_thread = None

        for thread in poll_threads:
            if thread.is_alive():
                thread.join(timeout=2)

    def update_heartbeat(self, device_id: str):
        """Record an authenticated device activity heartbeat."""

        with self._lock:
            if device_id not in self._devices:
                return

            self._last_heartbeat[device_id] = time.monotonic()
            self._unresponsive_devices.discard(device_id)

    # --------------------------------------------------------
    # MALFORMED MESSAGE HANDLING
    # --------------------------------------------------------

    def on_malformed(
        self,
        device_id: str,
        raw: Any,
    ) -> bool:
        """Reject an invalid message without crashing the transport."""

        logger.warning(
            "Rejected malformed message from '%s': %s",
            device_id,
            repr(raw)[:200],
        )

        return True

    # --------------------------------------------------------
    # DEVICE STATUS / LIST
    # --------------------------------------------------------

    def get_device_status(
        self,
        device_id: str,
    ) -> Optional[str]:
        with self._lock:
            if device_id not in self._devices:
                return None

            last_heartbeat = self._last_heartbeat.get(
                device_id
            )

            unresponsive = (
                device_id in self._unresponsive_devices
            )

        if (
            last_heartbeat is None
            or time.monotonic() - last_heartbeat
            > 2 * self.heartbeat_interval
            or unresponsive
        ):
            return "unresponsive"

        return "online"

    def list_devices(self) -> List[Dict[str, Any]]:
        """Return registered device details without exposing credentials."""

        with self._lock:
            device_items = list(self._devices.items())

            result = []

            for device_id, device in device_items:
                latest = self._latest_readings.get(device_id)

                result.append({
                    "device_id": device_id,
                    "protocol": getattr(
                        device,
                        "protocol",
                        "UNKNOWN",
                    ),
                    "capabilities": sorted(
                        self._capabilities.get(
                            device_id,
                            set(),
                        )
                    ),
                    "authenticated": self._authenticated.get(
                        device_id,
                        False,
                    ),
                    "status": self.get_device_status(device_id),
                    "has_sensor_data": latest is not None,
                    "last_data_timestamp": (
                        latest.get("timestamp")
                        if latest
                        else None
                    ),
                })

        return result
