"""
Property 32: Disconnected control-signal queueing
Validates: Requirements 12.3

Signals queued while device disconnected; returned in priority order.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from iot_layer import IoTIntegrationLayer, HandshakeResult, queue_control_signal, get_queued_signals
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


def _setup(tmp_path, device_id="dev_q"):
    database.DATABASE_PATH = Path(tmp_path / "queue.db")
    database.initialize_database()
    layer = IoTIntegrationLayer()
    layer.register_device(_StubDevice(device_id, {"vibration"}))
    return layer


@pytest.mark.skipif(not _HAS_IOT, reason="iot_layer not available")
def test_signal_queued_while_offline(tmp_path):
    orig = database.DATABASE_PATH
    try:
        layer = _setup(tmp_path)
        layer.on_disconnect("dev_q")
        queue_control_signal(device_id="dev_q", intent="SHUTDOWN", priority=10)
        rows = get_queued_signals("dev_q")
        assert len(rows) >= 1
    finally:
        database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT, reason="iot_layer not available")
def test_multiple_signals_queued(tmp_path):
    orig = database.DATABASE_PATH
    try:
        layer = _setup(tmp_path)
        layer.on_disconnect("dev_q")
        for intent, priority in [("SHUTDOWN", 10), ("DE_RATE", 5), ("RUN", 1)]:
            queue_control_signal(device_id="dev_q", intent=intent, priority=priority)
        rows = get_queued_signals("dev_q")
        assert len(rows) == 3
    finally:
        database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_IOT, reason="iot_layer not available")
def test_priority_order_highest_first(tmp_path):
    orig = database.DATABASE_PATH
    try:
        layer = _setup(tmp_path)
        queue_control_signal(device_id="dev_q", intent="RUN", priority=1)
        queue_control_signal(device_id="dev_q", intent="SHUTDOWN", priority=10)
        queue_control_signal(device_id="dev_q", intent="DE_RATE", priority=5)
        rows = get_queued_signals("dev_q")
        priorities = [r["priority"] for r in rows]
        assert priorities == sorted(priorities, reverse=True)
    finally:
        database.DATABASE_PATH = orig
