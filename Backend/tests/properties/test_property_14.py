"""
Property 14: Control-signal acknowledgement persistence.
Validates: Req 3.8

On equipment ack, record ack_timestamp + resulting equipment state in the
control_signals row.
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
    _HAS_ACK = hasattr(EquipmentController, "on_ack")
except ImportError:
    _HAS_EC = False
    _HAS_ACK = False

try:
    import database as _db_module
    _HAS_DB = True
except ImportError:
    _HAS_DB = False

ADMIN_SESSION = {"role": "ADMIN", "username": "test_admin"}


def _setup_db(tmp_dir, suffix="ack"):
    """Point database module at a fresh temp DB and return the original path."""
    import database
    from pathlib import Path
    orig = database.DATABASE_PATH
    database.DATABASE_PATH = Path(os.path.join(tmp_dir, f"{suffix}.db"))
    database.initialize_database()
    return orig


def _get_control_signal_row(control_signal_id):
    """Fetch a control_signals row by id."""
    import database
    conn = database.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM control_signals WHERE id = ?",
            (control_signal_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


@pytest.mark.skipif(not _HAS_EC or not _HAS_ACK or not _HAS_DB,
                    reason="EquipmentController.on_ack or database not available")
def test_ack_recorded():
    """Dispatch then acknowledge; ack_timestamp must be set in control_signals row."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = _setup_db(tmp)
        try:
            ec = EquipmentController()

            result = ec.dispatch(
                intent="SHUTDOWN",
                status="CRITICAL",
                session=ADMIN_SESSION,
            )
            control_id = result["control_signal_id"]

            # Confirm ack_timestamp is initially NULL.
            row_before = _get_control_signal_row(control_id)
            assert row_before is not None, "control_signals row must exist after dispatch"
            assert not row_before.get("ack_timestamp"), (
                "ack_timestamp must be NULL before acknowledgement"
            )

            # Acknowledge the signal.
            saved = ec.on_ack(control_signal_id=control_id, equipment_state="STOPPED")
            assert saved is True, "on_ack must return True on success"

            # Verify ack_timestamp was written.
            row_after = _get_control_signal_row(control_id)
            assert row_after is not None
            assert row_after.get("ack_timestamp"), (
                "ack_timestamp must be set after on_ack (Req 3.8)"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_EC or not _HAS_ACK or not _HAS_DB,
                    reason="EquipmentController.on_ack or database not available")
def test_ack_stores_equipment_state():
    """Acknowledge with state='RUNNING'; assert resulting_equipment_state is stored."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = _setup_db(tmp, "state_test")
        try:
            ec = EquipmentController()

            result = ec.dispatch(
                intent="DE_RATE",
                status="WARNING",
                session=ADMIN_SESSION,
            )
            control_id = result["control_signal_id"]

            ec.on_ack(control_signal_id=control_id, equipment_state="RUNNING")

            row = _get_control_signal_row(control_id)
            assert row is not None
            assert row.get("resulting_equipment_state") == "RUNNING", (
                "resulting_equipment_state must be persisted as 'RUNNING' (Req 3.8)"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_EC or not _HAS_ACK or not _HAS_DB,
                    reason="EquipmentController.on_ack or database not available")
def test_ack_removes_from_pending():
    """on_ack must remove the control_signal_id from the pending acks tracker."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = _setup_db(tmp, "pending_test")
        try:
            ec = EquipmentController()

            result = ec.dispatch(
                intent="SHUTDOWN",
                status="CRITICAL",
                session=ADMIN_SESSION,
            )
            control_id = result["control_signal_id"]

            # The id should be in _pending_acks after dispatch.
            assert control_id in ec._pending_acks, (
                "control_signal_id must be tracked in _pending_acks after dispatch"
            )

            ec.on_ack(control_signal_id=control_id, equipment_state="STOPPED")

            assert control_id not in ec._pending_acks, (
                "control_signal_id must be removed from _pending_acks after on_ack"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_EC or not _HAS_ACK or not _HAS_DB,
                    reason="hypothesis, equipment_controller, or database not available")
@given(equipment_state=st.sampled_from(["RUNNING", "STOPPED", "DE_RATED", "IDLE"]))
@settings(max_examples=100)
def test_property_ack_state_persisted(equipment_state):
    """Property: on_ack always persists the provided equipment_state string."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = database.DATABASE_PATH
        try:
            from pathlib import Path
            database.DATABASE_PATH = Path(
                os.path.join(tmp, f"prop_{equipment_state}.db")
            )
            database.initialize_database()
            ec = EquipmentController()

            result = ec.dispatch(
                intent="SHUTDOWN",
                status="CRITICAL",
                session=ADMIN_SESSION,
            )
            control_id = result["control_signal_id"]
            ec.on_ack(control_signal_id=control_id, equipment_state=equipment_state)

            row = _get_control_signal_row(control_id)
            assert row is not None
            assert row.get("resulting_equipment_state") == equipment_state, (
                f"resulting_equipment_state should be {equipment_state!r}"
            )
        finally:
            database.DATABASE_PATH = orig
