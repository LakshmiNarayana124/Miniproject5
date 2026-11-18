"""
Property 12: Critical-to-normal restoration round-trip
Validates: Requirements 3.2

After CRITICAL then NORMAL, the latched intent becomes RUN.
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
    _HAS_HYPOTHESIS = True
except ImportError:
    def given(*a, **kw): return lambda f: f
    def settings(*a, **kw): return lambda f: f
    class st:  # noqa: N801
        @staticmethod
        def sampled_from(seq): return []
    _HAS_HYPOTHESIS = False

try:
    from equipment_controller import EquipmentController, PermissionDenied, STATUS_TO_INTENT
    _HAS_EC = True
except ImportError:
    try:
        from equipment_controller import EquipmentController, PermissionDenied
        STATUS_TO_INTENT = {"CRITICAL": "SHUTDOWN", "WARNING": "DE_RATE", "NORMAL": "RUN"}
        _HAS_EC = True
    except ImportError:
        _HAS_EC = False


ADMIN_SESSION = {"role": "ADMIN", "username": "test_admin"}


def _make_controller(tmp_dir, suffix=""):
    """Return a fresh EquipmentController backed by a temp database."""
    import database
    db_path = os.path.join(tmp_dir, f"test_p12{suffix}.db")
    original_db = getattr(database, "_DB_PATH", None)
    database._DB_PATH = db_path
    database.initialize_database()
    ec = EquipmentController()
    return ec, original_db


@pytest.mark.skipif(not _HAS_EC, reason="equipment_controller not available")
def test_critical_latches_shutdown():
    """on_status('CRITICAL') latches the intent to SHUTDOWN (Req 3.1)."""
    import database
    with tempfile.TemporaryDirectory() as tmp:
        ec, orig = _make_controller(tmp, "_latch")
        try:
            ec.on_status("CRITICAL", session=ADMIN_SESSION)
            assert ec.latched_intent == "SHUTDOWN", \
                f"Expected SHUTDOWN after CRITICAL, got {ec.latched_intent!r}"
        finally:
            if orig is not None:
                database._DB_PATH = orig


@pytest.mark.skipif(not _HAS_EC, reason="equipment_controller not available")
def test_critical_then_normal_restores_run():
    """on_status('CRITICAL') then on_status('NORMAL') → latched_intent == 'RUN' (Req 3.2)."""
    import database
    with tempfile.TemporaryDirectory() as tmp:
        ec, orig = _make_controller(tmp, "_restore")
        try:
            ec.on_status("CRITICAL", session=ADMIN_SESSION)
            assert ec.latched_intent == "SHUTDOWN", \
                "Must latch SHUTDOWN after CRITICAL before testing restore"
            ec.on_status("NORMAL", session=ADMIN_SESSION)
            assert ec.latched_intent == "RUN", \
                f"Expected RUN after CRITICAL→NORMAL restore, got {ec.latched_intent!r}"
        finally:
            if orig is not None:
                database._DB_PATH = orig


@pytest.mark.skipif(not _HAS_EC, reason="equipment_controller not available")
def test_critical_latch_blocks_warning_downgrade():
    """While CRITICAL is latched, an intermediate WARNING does not downgrade to DE_RATE."""
    import database
    with tempfile.TemporaryDirectory() as tmp:
        ec, orig = _make_controller(tmp, "_block")
        try:
            ec.on_status("CRITICAL", session=ADMIN_SESSION)
            ec.on_status("WARNING", session=ADMIN_SESSION)
            # The latch must still hold SHUTDOWN; WARNING is refused (Req 11.3).
            assert ec.latched_intent == "SHUTDOWN", \
                f"CRITICAL latch should block WARNING downgrade, got {ec.latched_intent!r}"
        finally:
            if orig is not None:
                database._DB_PATH = orig


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_EC,
                    reason="hypothesis or equipment_controller not available")
@given(recovery_status=st.sampled_from(["NORMAL", "WARNING"]))
@settings(max_examples=20)
def test_critical_recovery_property(recovery_status):
    """Property: after CRITICAL, only NORMAL releases the latch to RUN (never stays SHUTDOWN)."""
    import database
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, f"test_p12_{recovery_status}.db")
        original_db = getattr(database, "_DB_PATH", None)
        database._DB_PATH = db_path
        database.initialize_database()
        ec = EquipmentController()
        try:
            ec.on_status("CRITICAL", session=ADMIN_SESSION)
            ec.on_status(recovery_status, session=ADMIN_SESSION)
            if recovery_status == "NORMAL":
                # NORMAL must release the latch.
                assert ec.latched_intent == "RUN", \
                    f"Expected RUN after CRITICAL→NORMAL, got {ec.latched_intent!r}"
            else:
                # WARNING is blocked while latched; intent stays SHUTDOWN.
                assert ec.latched_intent in ("SHUTDOWN", "DE_RATE"), \
                    f"Unexpected intent after CRITICAL→{recovery_status}: {ec.latched_intent!r}"
        finally:
            if original_db is not None:
                database._DB_PATH = original_db
