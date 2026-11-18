"""
Property 18: Reconnect session resumption
Validates: Requirements 4.7

On reconnect: re-establish session and resume data/command exchange.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from iot_layer import IoTIntegrationLayer, HandshakeResult
    import database
    _HAS_IOT = True
except ImportError:
    _HAS_IOT = False


class _StubDevice:
    def __init__(self, device_id, capabilities, protocol="MQTT"):
        self.device_id = device_id
        self.capabilities = set(capabilities)
        self.protocol = protocol

    def set_device_credential(self, cred): pass
    def set_message_handler(self, h): pass
    def connect(self):
        return HandshakeResult(True, self.device_id, self.capabilities, self.protocol)
    def recv_data(self): return b""
    def send_command(self, intent):
        from iot_layer import Ack
        return Ack(self.device_id, intent, "2024-01-01T00:00:00+00:00", "SENT")
    def disconnect(self): pass


def _setup(tmp_path, device_id="dev_rc"):
    database.DATABASE_PATH = Path(tmp_path / "rc.db")
    database.initialize_database()
    layer = IoTIntegrationLayer()
    result = layer.register_device(_StubDevice(device_id, {"vibration"}))
    return layer, result


@pytest.mark.skipif(not _HAS_IOT, reason="iot_layer not available")
def test_reconnect_marks_online(tmp_path):
    orig = database.DATABASE_PATH
    try:
        layer, _ = _setup(tmp_path)
        layer.on_disconnect("dev_rc")
        layer.on_reconnect("dev_rc")
        status = layer.get_device_status("dev_rc")
        assert status != "offline"
    finally:
        database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT, reason="iot_layer not available")
def test_data_accepted_after_reconnect(tmp_path):
    orig = database.DATABASE_PATH
    try:
        layer, _ = _setup(tmp_path)
        layer.on_disconnect("dev_rc")
        layer.on_reconnect("dev_rc")
        try:
            layer.on_data("dev_rc", b'{"vibration":{"value":0.1,"unit":"g","quality":"GOOD"}}',
                          credential=None)
        except Exception as exc:
            pytest.fail(f"on_data raised after reconnect: {exc}")
    finally:
        database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT, reason="iot_layer not available")
def test_multiple_cycles(tmp_path):
    orig = database.DATABASE_PATH
    try:
        layer, _ = _setup(tmp_path)
        for _ in range(3):
            layer.on_disconnect("dev_rc")
            layer.on_reconnect("dev_rc")
        status = layer.get_device_status("dev_rc")
        assert status != "offline"
    finally:
        database.DATABASE_PATH = orig
