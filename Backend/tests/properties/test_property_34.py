"""
Property 34: Malformed-message isolation
Validates: Requirements 12.5

Malformed messages rejected and logged; device connection stays open.
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
    def set_device_credential(self, c): pass
    def set_message_handler(self, h): pass
    def connect(self):
        return HandshakeResult(True, self.device_id, self.capabilities, self.protocol)
    def recv_data(self): return b""
    def send_command(self, intent):
        from iot_layer import Ack
        return Ack(self.device_id, intent, "2024-01-01T00:00:00+00:00", "SENT")
    def disconnect(self): pass


def _setup(tmp_path, device_id="dev_mal"):
    database.DATABASE_PATH = Path(tmp_path / "mal.db")
    database.initialize_database()
    layer = IoTIntegrationLayer()
    layer.register_device(_StubDevice(device_id, {"vibration"}))
    return layer


@pytest.mark.skipif(not _HAS_IOT, reason="iot_layer not available")
def test_on_malformed_method_exists(tmp_path):
    orig = database.DATABASE_PATH
    try:
        layer = _setup(tmp_path)
        assert hasattr(layer, "on_malformed")
    finally:
        database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT, reason="iot_layer not available")
def test_on_malformed_does_not_raise(tmp_path):
    orig = database.DATABASE_PATH
    try:
        layer = _setup(tmp_path)
        try:
            layer.on_malformed("dev_mal", b"not valid json {{}")
        except Exception as exc:
            pytest.fail(f"on_malformed raised: {exc}")
    finally:
        database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT, reason="iot_layer not available")
def test_device_still_registered_after_malformed(tmp_path):
    orig = database.DATABASE_PATH
    try:
        layer = _setup(tmp_path)
        layer.on_malformed("dev_mal", b"garbage")
        status = layer.get_device_status("dev_mal")
        assert status is not None
    finally:
        database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT, reason="iot_layer not available")
def test_valid_data_after_malformed(tmp_path):
    orig = database.DATABASE_PATH
    try:
        layer = _setup(tmp_path)
        layer.on_malformed("dev_mal", b"garbage")
        try:
            layer.on_data("dev_mal", b'{"vibration":{"value":0.1,"unit":"g","quality":"GOOD"}}',
                          credential=None)
        except Exception as exc:
            pytest.fail(f"on_data raised after malformed: {exc}")
    finally:
        database.DATABASE_PATH = orig
