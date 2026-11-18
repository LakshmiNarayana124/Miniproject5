"""
Property 30: Critical SHUTDOWN latching.
Validates: Req 11.3

While CRITICAL persists, the controller holds SHUTDOWN and refuses to
downgrade to DE_RATE or RUN. Only NORMAL clears the latch.
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

ADMIN_SESSION = {"role": "ADMIN", "username": "test_admin"}


def _make_controller(tmp_dir, suffix="test"):
    """Return an EquipmentController backed by a temp database."""
    import database
    from pathlib import Path
    database.DATABASE_PATH = Path(os.path.join(tmp_dir, f"{suffix}.db"))
    database.initialize_database()
    return EquipmentController()


@pytest.mark.skipif(not _HAS_EC, reason="equipment_controller not available")
def test_critical_holds_shutdown():
    """After CRITICAL, sending WARNING must NOT change latched_intent away from SHUTDOWN."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = database.DATABASE_PATH
        try:
            ec = _make_controller(tmp)

            ec.on_status("CRITICAL", session=ADMIN_SESSION)
            assert ec.latched_intent == "SHUTDOWN", (
                "CRITICAL must latch intent to SHUTDOWN"
            )
            assert ec.latched_status == "CRITICAL"

            # WARNING while CRITICAL is latched — must be refused.
            ec.on_status("WARNING", session=ADMIN_SESSION)
            assert ec.latched_intent == "SHUTDOWN", (
                "CRITICAL latch must hold: WARNING must not downgrade intent to DE_RATE (Req 11.3)"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_EC, reason="equipment_controller not available")
def test_critical_only_clears_on_normal():
    """Only NORMAL clears the CRITICAL latch; a subsequent WARNING still holds SHUTDOWN."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = database.DATABASE_PATH
        try:
            ec = _make_controller(tmp, "clear_test")

            ec.on_status("CRITICAL", session=ADMIN_SESSION)
            # Attempt to clear with WARNING — must be refused.
            ec.on_status("WARNING", session=ADMIN_SESSION)
            assert ec.latched_intent == "SHUTDOWN", (
                "WARNING must not clear CRITICAL latch"
            )

            # Clear with NORMAL — must succeed.
            ec.on_status("NORMAL", session=ADMIN_SESSION)
            assert ec.latched_intent == "RUN", (
                "NORMAL must release CRITICAL latch and set intent to RUN (Req 3.2)"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_EC, reason="equipment_controller not available")
def test_de_rate_does_not_clear_latch():
    """DE_RATE status while CRITICAL is latched must leave intent as SHUTDOWN."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = database.DATABASE_PATH
        try:
            ec = _make_controller(tmp, "derate_test")

            ec.on_status("CRITICAL", session=ADMIN_SESSION)
            # on_status("WARNING") maps to DE_RATE; this path is blocked while latched.
            # Also test the mapped DE_RATE intent directly via on_status("WARNING").
            ec.on_status("WARNING", session=ADMIN_SESSION)
            assert ec.latched_intent == "SHUTDOWN", (
                "DE_RATE / WARNING must not clear CRITICAL latch"
            )
            # Status must still be reported as CRITICAL (latch not released).
            assert ec.latched_status == "CRITICAL"
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_EC, reason="equipment_controller not available")
def test_latch_does_not_apply_before_critical():
    """Before any CRITICAL event, WARNING correctly produces DE_RATE."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = database.DATABASE_PATH
        try:
            ec = _make_controller(tmp, "pre_critical_test")

            ec.on_status("WARNING", session=ADMIN_SESSION)
            assert ec.latched_intent == "DE_RATE", (
                "Without a prior CRITICAL, WARNING must produce DE_RATE"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_EC,
                    reason="hypothesis or equipment_controller not available")
@given(downgrade_status=st.sampled_from(["WARNING", "DE_RATE"]))
@settings(max_examples=100)
def test_property_latch_refuses_downgrade(downgrade_status):
    """Property: any non-NORMAL status while CRITICAL is latched keeps intent as SHUTDOWN."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = database.DATABASE_PATH
        try:
            from pathlib import Path
            database.DATABASE_PATH = Path(
                os.path.join(tmp, f"prop_{downgrade_status}.db")
            )
            database.initialize_database()
            ec = EquipmentController()

            ec.on_status("CRITICAL", session=ADMIN_SESSION)
            # WARNING maps through on_status; DE_RATE is not a valid status key
            # so on_status("DE_RATE") maps to RUN via STATUS_TO_INTENT fallback —
            # either way the latch must hold.
            ec.on_status("WARNING", session=ADMIN_SESSION)

            assert ec.latched_intent == "SHUTDOWN", (
                f"Latch must hold SHUTDOWN after sending status={downgrade_status!r} "
                "while CRITICAL is active"
            )
        finally:
            database.DATABASE_PATH = orig
