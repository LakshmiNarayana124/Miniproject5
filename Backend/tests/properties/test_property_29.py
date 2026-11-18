"""
Property 29: SHUTDOWN delivery retry.
Validates: Req 11.2

_send_with_retry reattempts on transient failure and returns success once
the channel recovers.
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
    from equipment_controller import EquipmentController
    _HAS_EC = True
except ImportError:
    _HAS_EC = False

try:
    from unittest.mock import MagicMock, patch, call
    _HAS_MOCK = True
except ImportError:
    _HAS_MOCK = False

ADMIN_SESSION = {"role": "ADMIN", "username": "test_admin"}


def _make_controller(tmp_dir):
    """Return an EquipmentController backed by a temp database."""
    import database
    from pathlib import Path
    db_path = Path(os.path.join(tmp_dir, "test.db"))
    orig = database.DATABASE_PATH
    database.DATABASE_PATH = db_path
    database.initialize_database()
    ec = EquipmentController()
    return ec, orig


@pytest.mark.skipif(not _HAS_EC or not _HAS_MOCK,
                    reason="equipment_controller or unittest.mock not available")
def test_retry_succeeds_after_failure():
    """mock the iot_layer to fail twice then succeed; dispatch must return delivered=True."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        from pathlib import Path
        orig = database.DATABASE_PATH
        try:
            ec, _ = _make_controller(tmp)

            # Create a fake iot_layer whose relay fails twice then succeeds.
            call_count = {"n": 0}

            def flaky_relay(intent):
                call_count["n"] += 1
                if call_count["n"] < 3:
                    raise RuntimeError("transient network error")

            mock_iot = MagicMock()
            mock_iot.relay.side_effect = flaky_relay
            ec.iot_layer = mock_iot
            ec.max_retries = 5
            ec.retry_delay_s = 0.0

            result = ec.dispatch(
                intent="SHUTDOWN",
                status="CRITICAL",
                session=ADMIN_SESSION,
            )

            assert result["delivered"] is True, (
                "dispatch must report delivered=True after transient failures recover"
            )
            assert call_count["n"] == 3, (
                "relay should be called exactly 3 times (2 failures + 1 success)"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_EC or not _HAS_MOCK,
                    reason="equipment_controller or unittest.mock not available")
def test_retry_count_bounded():
    """Retries must not exceed max_retries (here set to 5)."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        from pathlib import Path
        orig = database.DATABASE_PATH
        try:
            ec, _ = _make_controller(tmp)

            call_count = {"n": 0}

            def always_fail(intent):
                call_count["n"] += 1
                raise RuntimeError("persistent failure")

            mock_iot = MagicMock()
            mock_iot.relay.side_effect = always_fail

            max_retries = 5
            ec.iot_layer = mock_iot
            ec.max_retries = max_retries
            ec.retry_delay_s = 0.0

            result = ec.dispatch(
                intent="SHUTDOWN",
                status="CRITICAL",
                session=ADMIN_SESSION,
            )

            assert result["delivered"] is False, (
                "dispatch must report delivered=False when all retries fail"
            )
            assert call_count["n"] <= max_retries, (
                f"relay was called {call_count['n']} times, exceeding max_retries={max_retries}"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_EC or not _HAS_MOCK,
                    reason="equipment_controller or unittest.mock not available")
def test_retry_succeeds_on_first_attempt():
    """When the channel is healthy from the start, only one send attempt is made."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = database.DATABASE_PATH
        try:
            ec, _ = _make_controller(tmp)

            call_count = {"n": 0}

            def success_relay(intent):
                call_count["n"] += 1

            mock_iot = MagicMock()
            mock_iot.relay.side_effect = success_relay
            ec.iot_layer = mock_iot
            ec.max_retries = 3
            ec.retry_delay_s = 0.0

            result = ec.dispatch(
                intent="DE_RATE",
                status="WARNING",
                session=ADMIN_SESSION,
            )

            assert result["delivered"] is True
            assert call_count["n"] == 1, (
                "A successful first attempt must not be retried"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_EC or not _HAS_MOCK,
                    reason="hypothesis, equipment_controller, or mock not available")
@given(fail_count=st.integers(min_value=0, max_value=4))
@settings(max_examples=100)
def test_retry_delivers_when_enough_attempts_remain(fail_count):
    """Property: dispatch succeeds whenever failures < max_retries."""
    assume(fail_count < 5)
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = database.DATABASE_PATH
        try:
            from pathlib import Path
            database.DATABASE_PATH = Path(os.path.join(tmp, f"test_{fail_count}.db"))
            database.initialize_database()
            ec = EquipmentController()

            calls = {"n": 0}

            def relay_with_failures(intent):
                calls["n"] += 1
                if calls["n"] <= fail_count:
                    raise RuntimeError("transient")

            mock_iot = MagicMock()
            mock_iot.relay.side_effect = relay_with_failures
            ec.iot_layer = mock_iot
            ec.max_retries = 5
            ec.retry_delay_s = 0.0

            result = ec.dispatch(
                intent="SHUTDOWN",
                status="CRITICAL",
                session=ADMIN_SESSION,
            )

            assert result["delivered"] is True, (
                f"Should deliver when fail_count={fail_count} < max_retries=5"
            )
        finally:
            database.DATABASE_PATH = orig
