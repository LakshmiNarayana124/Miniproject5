"""
Property 16: Device data forwarding fidelity.
Validates: Req 4.4

The payload forwarded to the inference callback equals the payload received
from the device (verbatim bytes, not re-encoded).
"""
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from hypothesis import given, settings, assume
    from hypothesis import strategies as st
    _HAS_HYPOTHESIS = True
except ImportError:
    def given(*a, **kw): return lambda f: f
    def settings(*a, **kw): return lambda f: f
    def assume(c): pass
    class st:
        @staticmethod
        def sampled_from(s): return []
        @staticmethod
        def booleans(): return []
        @staticmethod
        def integers(*a, **kw): return []
    _HAS_HYPOTHESIS = False

try:
    from iot_layer import IoTIntegrationLayer, HandshakeResult
    _HAS_IOT = True
except ImportError:
    _HAS_IOT = False

try:
    from unittest.mock import MagicMock
    _HAS_MOCK = True
except ImportError:
    _HAS_MOCK = False

try:
    import database as _db_module
    _HAS_DB = True
except ImportError:
    _HAS_DB = False


# ---------------------------------------------------------------------------
# Stub device (same as test_property_15 — keep each file standalone)
# ---------------------------------------------------------------------------

class _StubDevice:
    def __init__(self, device_id, capabilities=None, protocol="MQTT"):
        self.device_id = device_id
        self.capabilities = set(capabilities or {"vibration"})
        self.protocol = protocol
        self._credential = None

    def set_device_credential(self, cred):
        self._credential = cred

    def set_message_handler(self, handler):
        pass

    def connect(self):
        return HandshakeResult(
            success=True,
            device_id=self.device_id,
            capabilities=self.capabilities,
            protocol=self.protocol,
        )

    def recv_data(self) -> bytes:
        return b""

    def send_command(self, intent: str):
        from iot_layer import Ack
        return Ack(self.device_id, intent, "2024-01-01T00:00:00+00:00", "SENT")

    def disconnect(self):
        pass


def _make_valid_payload_bytes():
    """Return a valid authenticated sensor payload as bytes."""
    return json.dumps({
        "vibration": {
            "value": 0.42,
            "unit": "g",
            "quality": "GOOD",
        }
    }).encode("utf-8")


def _register_and_authenticate(layer, device_id="fwd-dev-001"):
    """Register a stub device and return its credential."""
    device = _StubDevice(device_id, {"vibration"}, "MQTT")
    result = layer.register_device(device)
    assert result.success, f"Device registration failed: {result.reason}"
    return result.device_credential


def _setup_db(tmp_dir, suffix="fwd"):
    import database
    from pathlib import Path
    orig = database.DATABASE_PATH
    database.DATABASE_PATH = Path(os.path.join(tmp_dir, f"{suffix}.db"))
    database.initialize_database()
    return orig


@pytest.mark.skipif(not _HAS_IOT or not _HAS_MOCK or not _HAS_DB,
                    reason="iot_layer, unittest.mock, or database not available")
def test_payload_forwarded_verbatim():
    """on_data must forward the original payload bytes verbatim to the inference callback."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = _setup_db(tmp)
        try:
            captured = []
            callback = MagicMock(side_effect=lambda did, raw: captured.append((did, raw)))

            layer = IoTIntegrationLayer(inference_callback=callback)
            credential = _register_and_authenticate(layer)

            payload = _make_valid_payload_bytes()
            accepted = layer.on_data("fwd-dev-001", payload, credential=credential)

            assert accepted is True, "on_data must accept a valid authenticated payload"
            assert len(captured) == 1, (
                "Inference callback must be called exactly once per on_data invocation"
            )
            forwarded_device_id, forwarded_payload = captured[0]
            assert forwarded_device_id == "fwd-dev-001", (
                "Forwarded device_id must match the registering device"
            )
            assert forwarded_payload == payload, (
                "Forwarded payload bytes must be identical to the received bytes (Req 4.4)"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT or not _HAS_MOCK or not _HAS_DB,
                    reason="iot_layer, unittest.mock, or database not available")
def test_payload_not_forwarded_without_authentication():
    """Unauthenticated on_data must not invoke the inference callback."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = _setup_db(tmp, "unauth_test")
        try:
            callback = MagicMock()
            layer = IoTIntegrationLayer(inference_callback=callback)
            # Register without authenticating.
            _register_and_authenticate(layer, "fwd-dev-002")

            payload = _make_valid_payload_bytes()
            accepted = layer.on_data("fwd-dev-002", payload, credential="wrong-credential")

            assert accepted is False, (
                "on_data with wrong credential must be rejected"
            )
            callback.assert_not_called()
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT or not _HAS_MOCK or not _HAS_DB,
                    reason="iot_layer, unittest.mock, or database not available")
def test_payload_not_forwarded_for_unknown_device():
    """on_data for an unregistered device must not invoke the inference callback."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = _setup_db(tmp, "unknown_test")
        try:
            callback = MagicMock()
            layer = IoTIntegrationLayer(inference_callback=callback)

            payload = _make_valid_payload_bytes()
            accepted = layer.on_data("ghost-device", payload, credential="any")

            assert accepted is False
            callback.assert_not_called()
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_IOT or not _HAS_MOCK or not _HAS_DB,
                    reason="hypothesis, iot_layer, mock, or database not available")
@given(value=st.integers(min_value=0, max_value=100))
@settings(max_examples=20, deadline=None)
def test_property_forwarded_bytes_equal_received(value):
    """Property: for any valid sensor value the forwarded bytes equal the received bytes."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = database.DATABASE_PATH
        try:
            from pathlib import Path
            database.DATABASE_PATH = Path(
                os.path.join(tmp, f"prop_fwd_{value}.db")
            )
            database.initialize_database()

            captured = []
            callback = MagicMock(side_effect=lambda d, r: captured.append(r))

            layer = IoTIntegrationLayer(inference_callback=callback)
            device = _StubDevice("prop-dev-001", {"vibration"}, "MQTT")
            reg = layer.register_device(device)
            assume(reg.success)

            payload = json.dumps({
                "vibration": {
                    "value": float(value),
                    "unit": "g",
                    "quality": "GOOD",
                }
            }).encode("utf-8")

            accepted = layer.on_data("prop-dev-001", payload, credential=reg.device_credential)
            assume(accepted)

            assert len(captured) == 1
            assert captured[0] == payload, (
                "Inference callback must receive the exact original bytes"
            )
        finally:
            database.DATABASE_PATH = orig
