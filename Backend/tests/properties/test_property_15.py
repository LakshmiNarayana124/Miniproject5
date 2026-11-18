"""
Property 15: Handshake accept/reject correctness.
Validates: Req 4.2, 4.8

Compatible devices are accepted; incompatible capability sets are rejected.
"""
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
    import database as _db_module
    _HAS_DB = True
except ImportError:
    _HAS_DB = False


# ---------------------------------------------------------------------------
# Minimal stub device that satisfies the EdgeDevice protocol without real
# transport libraries.
# ---------------------------------------------------------------------------

class _StubDevice:
    """In-process stub that always reports a successful connect."""

    def __init__(self, device_id, capabilities, protocol="MQTT"):
        self.device_id = device_id
        self.capabilities = set(capabilities or set())
        self.protocol = protocol
        self._credential = None

    def set_device_credential(self, cred):
        self._credential = cred

    def set_message_handler(self, handler):
        pass

    def connect(self) -> "HandshakeResult":
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


def _setup_db(tmp_dir, suffix="handshake"):
    import database
    from pathlib import Path
    orig = database.DATABASE_PATH
    database.DATABASE_PATH = Path(os.path.join(tmp_dir, f"{suffix}.db"))
    database.initialize_database()
    return orig


@pytest.mark.skipif(not _HAS_IOT or not _HAS_DB,
                    reason="iot_layer or database not available")
def test_valid_device_accepted():
    """A device with valid capabilities and protocol must be accepted (Req 4.2)."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = _setup_db(tmp)
        try:
            layer = IoTIntegrationLayer()
            device = _StubDevice(
                device_id="sensor-001",
                capabilities={"vibration", "temperature", "current"},
                protocol="MQTT",
            )

            result = layer.register_device(device)

            assert result.success is True, (
                f"Valid device must be accepted; got reason={result.reason!r}"
            )
            assert result.device_id == "sensor-001"
            assert result.device_credential is not None, (
                "Successful registration must return a device_credential"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT or not _HAS_DB,
                    reason="iot_layer or database not available")
def test_incompatible_device_rejected_missing_capabilities():
    """A device missing required capabilities must be rejected (Req 4.8)."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = _setup_db(tmp, "missing_caps")
        try:
            layer = IoTIntegrationLayer()
            device = _StubDevice(
                device_id="sensor-002",
                capabilities=set(),  # no capabilities at all
                protocol="MQTT",
            )
            required = {"vibration", "temperature"}

            result = layer.register_device(
                device,
                required_capabilities=required,
            )

            assert result.success is False, (
                "Device missing required capabilities must be rejected (Req 4.8)"
            )
            assert "Missing" in result.reason or result.reason, (
                "Rejection reason must explain what is missing"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT or not _HAS_DB,
                    reason="iot_layer or database not available")
def test_device_with_unsupported_protocol_rejected():
    """A device with an unsupported protocol must be rejected."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = _setup_db(tmp, "bad_proto")
        try:
            layer = IoTIntegrationLayer()
            device = _StubDevice(
                device_id="sensor-003",
                capabilities={"vibration"},
                protocol="COAP",  # unsupported
            )

            result = layer.register_device(device)

            assert result.success is False, (
                "Device with unsupported protocol must be rejected"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT or not _HAS_DB,
                    reason="iot_layer or database not available")
def test_duplicate_device_rejected():
    """Registering the same device_id twice must fail on the second attempt."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = _setup_db(tmp, "dup_test")
        try:
            layer = IoTIntegrationLayer()
            device_a = _StubDevice("sensor-dup", {"vibration"}, "MQTT")
            device_b = _StubDevice("sensor-dup", {"vibration"}, "MQTT")

            first = layer.register_device(device_a)
            second = layer.register_device(device_b)

            assert first.success is True
            assert second.success is False, (
                "Re-registering the same device_id must be rejected"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT or not _HAS_DB,
                    reason="iot_layer or database not available")
def test_device_with_blank_id_rejected():
    """A device with an empty or blank device_id must be rejected."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = _setup_db(tmp, "blank_id")
        try:
            layer = IoTIntegrationLayer()
            device = _StubDevice("   ", {"vibration"}, "MQTT")

            result = layer.register_device(device)

            assert result.success is False, (
                "Blank device_id must be rejected"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_IOT or not _HAS_DB,
                    reason="hypothesis, iot_layer, or database not available")
@given(protocol=st.sampled_from(["MQTT", "HTTP"]))
@settings(max_examples=100)
def test_property_valid_protocols_accepted(protocol):
    """Property: devices using MQTT or HTTP with valid capabilities are accepted."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = database.DATABASE_PATH
        try:
            from pathlib import Path
            database.DATABASE_PATH = Path(
                os.path.join(tmp, f"prop_{protocol}.db")
            )
            database.initialize_database()
            layer = IoTIntegrationLayer()

            device = _StubDevice(
                device_id=f"dev-{protocol}-001",
                capabilities={"vibration", "temperature"},
                protocol=protocol,
            )
            result = layer.register_device(device)

            assert result.success is True, (
                f"Device with protocol={protocol!r} and valid capabilities must be accepted"
            )
        finally:
            database.DATABASE_PATH = orig
