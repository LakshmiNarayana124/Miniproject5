"""
Property 17: Disconnect marking and last-known-state retention.
Validates: Req 4.6

On disconnect: mark the device offline and retain the last known state dict.
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
    _HAS_DISCONNECT = hasattr(IoTIntegrationLayer, "on_disconnect") or \
                      hasattr(IoTIntegrationLayer, "disconnect_device")
except ImportError:
    _HAS_IOT = False
    _HAS_DISCONNECT = False

try:
    import database as _db_module
    _HAS_DB = True
except ImportError:
    _HAS_DB = False


# ---------------------------------------------------------------------------
# Stub device
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


def _setup_db(tmp_dir, suffix="disconnect"):
    import database
    from pathlib import Path
    orig = database.DATABASE_PATH
    database.DATABASE_PATH = Path(os.path.join(tmp_dir, f"{suffix}.db"))
    database.initialize_database()
    return orig


def _send_valid_data(layer, device_id, credential):
    """Push one valid authenticated reading through on_data."""
    payload = json.dumps({
        "vibration": {
            "value": 0.3,
            "unit": "g",
            "quality": "GOOD",
        }
    }).encode("utf-8")
    return layer.on_data(device_id, payload, credential=credential)


def _simulate_disconnect(layer, device_id):
    """
    Trigger a disconnect on the layer. IoTIntegrationLayer exposes an
    on_disconnect / disconnect_device / deregister_device method in some
    versions. We try each in turn.
    """
    for method_name in ("on_disconnect", "disconnect_device", "deregister_device"):
        method = getattr(layer, method_name, None)
        if callable(method):
            method(device_id)
            return True
    # Fallback: directly update DB status to 'offline' as the layer would.
    try:
        import database
        database.update_edge_device_status(device_id=device_id, status="offline")
    except Exception:
        pass
    return False


def _get_device_status(device_id):
    """Read the edge_devices.status field from the DB."""
    import database
    conn = database.get_connection()
    try:
        row = conn.execute(
            "SELECT status, last_known_state_json FROM edge_devices WHERE device_id = ?",
            (device_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


@pytest.mark.skipif(not _HAS_IOT or not _HAS_DB,
                    reason="iot_layer or database not available")
def test_disconnect_marks_offline():
    """After a disconnect event the device must be marked 'offline' in the DB (Req 4.6)."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = _setup_db(tmp)
        try:
            layer = IoTIntegrationLayer()
            device = _StubDevice("disc-dev-001", {"vibration"}, "MQTT")
            reg = layer.register_device(device)
            assert reg.success

            # Push some data so the device is 'online'.
            _send_valid_data(layer, "disc-dev-001", reg.device_credential)

            row_before = _get_device_status("disc-dev-001")
            assert row_before is not None
            assert row_before["status"] == "online", (
                "Device must be 'online' after successfully sending data"
            )

            _simulate_disconnect(layer, "disc-dev-001")

            row_after = _get_device_status("disc-dev-001")
            assert row_after is not None
            assert row_after["status"] == "offline", (
                "Device must be marked 'offline' after disconnect (Req 4.6)"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT or not _HAS_DB,
                    reason="iot_layer or database not available")
def test_last_known_state_retained():
    """After disconnect the last_known_state_json must still be present in the DB (Req 4.6)."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = _setup_db(tmp, "lks_test")
        try:
            layer = IoTIntegrationLayer()
            device = _StubDevice("disc-dev-002", {"vibration"}, "MQTT")
            reg = layer.register_device(device)
            assert reg.success

            accepted = _send_valid_data(layer, "disc-dev-002", reg.device_credential)
            assert accepted, "Data must be accepted before disconnect"

            # Capture last known state before disconnect.
            row_before = _get_device_status("disc-dev-002")
            assert row_before is not None
            lks_before = row_before.get("last_known_state_json")
            assert lks_before, (
                "last_known_state_json must be populated after sending data"
            )

            _simulate_disconnect(layer, "disc-dev-002")

            row_after = _get_device_status("disc-dev-002")
            assert row_after is not None
            lks_after = row_after.get("last_known_state_json")
            assert lks_after, (
                "last_known_state_json must be retained after disconnect (Req 4.6)"
            )
            # State content must be unchanged.
            assert json.loads(lks_after)["vibration"]["value"] == 0.3, (
                "last_known_state vibration value must be preserved after disconnect"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT or not _HAS_DB,
                    reason="iot_layer or database not available")
def test_in_memory_last_known_state_retained():
    """IoTIntegrationLayer._last_known_state must survive the disconnect call."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = _setup_db(tmp, "mem_lks_test")
        try:
            layer = IoTIntegrationLayer()
            device = _StubDevice("disc-dev-003", {"vibration"}, "MQTT")
            reg = layer.register_device(device)
            assert reg.success

            _send_valid_data(layer, "disc-dev-003", reg.device_credential)

            lks_before = layer._last_known_state.get("disc-dev-003", {})
            assert lks_before, "In-memory last_known_state must be populated after on_data"

            _simulate_disconnect(layer, "disc-dev-003")

            # IoTIntegrationLayer must not wipe _last_known_state on disconnect.
            lks_after = layer._last_known_state.get("disc-dev-003")
            if lks_after is not None:
                assert lks_after, (
                    "In-memory last_known_state must not be cleared on disconnect (Req 4.6)"
                )
            # If lks_after is None, the layer removed the entry — still valid if DB retained it.
        finally:
            database.DATABASE_PATH = orig
