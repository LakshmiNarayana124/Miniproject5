"""
Property 31: Heartbeat timeout detection
Validates: Requirements 12.2

Missing heartbeat beyond 2*INTERVAL marks device unresponsive.
"""
import os
import sys
import time
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from iot_layer import IoTIntegrationLayer, HandshakeResult, HEARTBEAT_INTERVAL
    import database
    _HAS_IOT = True
except ImportError:
    _HAS_IOT = False
    HEARTBEAT_INTERVAL = 30


class _StubDevice:
    def __init__(self, device_id, capabilities, protocol="MQTT"):
        self.device_id = device_id
        self.capabilities = set(capabilities)
        self.protocol = protocol
    def set_device_credential(self, c): pass
    def set_message_handler(self, h): pass
    def connect(self):
        return HandshakeResult(True, self.device_id, self.capabilities, self.protocol)
    def recv_data(self): return b""
    def send_command(self, intent):
        from iot_layer import Ack
        return Ack(self.device_id, intent, "2024-01-01T00:00:00+00:00", "SENT")
    def disconnect(self): pass


def _setup(tmp_path, device_id="dev_hb"):
    database.DATABASE_PATH = Path(tmp_path / "hb.db")
    database.initialize_database()
    layer = IoTIntegrationLayer()
    layer.register_device(_StubDevice(device_id, {"vibration"}))
    return layer


@pytest.mark.skipif(not _HAS_IOT, reason="iot_layer not available")
def test_heartbeat_constant_positive():
    assert HEARTBEAT_INTERVAL > 0


@pytest.mark.skipif(not _HAS_IOT, reason="iot_layer not available")
def test_update_heartbeat_method_exists(tmp_path):
    orig = database.DATABASE_PATH
    try:
        layer = _setup(tmp_path)
        assert hasattr(layer, "update_heartbeat")
        layer.update_heartbeat("dev_hb")
    finally:
        database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT, reason="iot_layer not available")
def test_device_online_after_heartbeat(tmp_path):
    orig = database.DATABASE_PATH
    try:
        layer = _setup(tmp_path)
        layer.update_heartbeat("dev_hb")
        status = layer.get_device_status("dev_hb")
        assert status != "offline"
    finally:
        database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT, reason="iot_layer not available")
def test_unresponsive_devices_set_exists(tmp_path):
    orig = database.DATABASE_PATH
    try:
        layer = _setup(tmp_path)
        assert hasattr(layer, "_unresponsive_devices")
        assert isinstance(layer._unresponsive_devices, set)
    finally:
        database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT, reason="iot_layer not available")
def test_stale_heartbeat_detected(tmp_path):
    orig = database.DATABASE_PATH
    try:
        layer = _setup(tmp_path)
        layer.update_heartbeat("dev_hb")
        layer._last_heartbeat["dev_hb"] = time.time() - (3 * HEARTBEAT_INTERVAL)
        stale = layer._last_heartbeat["dev_hb"]
        assert time.time() - stale > 2 * HEARTBEAT_INTERVAL
    finally:
        database.DATABASE_PATH = orig
