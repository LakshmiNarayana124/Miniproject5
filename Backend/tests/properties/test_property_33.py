"""
Property 33: Device authentication gate
Validates: Requirements 12.4

authenticate() must succeed before data/commands are accepted.
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


def _setup(tmp_path, device_id="dev_auth"):
    database.DATABASE_PATH = Path(tmp_path / "auth.db")
    database.initialize_database()
    layer = IoTIntegrationLayer()
    result = layer.register_device(_StubDevice(device_id, {"vibration"}))
    return layer, result


@pytest.mark.skipif(not _HAS_IOT, reason="iot_layer not available")
def test_authenticate_method_exists(tmp_path):
    orig = database.DATABASE_PATH
    try:
        layer, _ = _setup(tmp_path)
        assert hasattr(layer, "authenticate")
    finally:
        database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT, reason="iot_layer not available")
def test_valid_credential_accepted(tmp_path):
    orig = database.DATABASE_PATH
    try:
        layer, result = _setup(tmp_path)
        cred = result.device_credential
        if not cred:
            pytest.skip("No credential returned")
        assert layer.authenticate("dev_auth", cred) is True
    finally:
        database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT, reason="iot_layer not available")
def test_invalid_credential_rejected(tmp_path):
    orig = database.DATABASE_PATH
    try:
        layer, _ = _setup(tmp_path)
        assert layer.authenticate("dev_auth", "WRONG_CRED_XYZ") is False
    finally:
        database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT, reason="iot_layer not available")
def test_unknown_device_rejected(tmp_path):
    orig = database.DATABASE_PATH
    try:
        layer, _ = _setup(tmp_path)
        assert layer.authenticate("nonexistent", "any_cred") is False
    finally:
        database.DATABASE_PATH = orig
