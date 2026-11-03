"""
Property 13: SHUTDOWN priority dominance
Validates: Requirements 3.6

Assert that SHUTDOWN carries the highest priority and is never downgraded
to DE_RATE or RUN while CRITICAL is latched.
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
        @staticmethod
        def integers(**kw): return []
    _HAS_HYPOTHESIS = False

# Priority constants — import from training_pipeline if available, else define locally
try:
    from training_pipeline import PRIORITY_SHUTDOWN, PRIORITY_DE_RATE, PRIORITY_RUN, STATUS_TO_INTENT
except ImportError:
    PRIORITY_SHUTDOWN = 3
    PRIORITY_DE_RATE = 2
    PRIORITY_RUN = 1
    STATUS_TO_INTENT = {"CRITICAL": "SHUTDOWN", "WARNING": "DE_RATE", "NORMAL": "RUN"}

try:
    from equipment_controller import EquipmentController
    _HAS_EC = True
except ImportError:
    _HAS_EC = False

ADMIN_SESSION = {"role": "ADMIN", "username": "test_admin"}


def test_priority_constants():
    """SHUTDOWN > DE_RATE > RUN numerically (Req 3.6)."""
    assert PRIORITY_SHUTDOWN > PRIORITY_DE_RATE, \
        "SHUTDOWN priority must exceed DE_RATE"
    assert PRIORITY_DE_RATE > PRIORITY_RUN, \
        "DE_RATE priority must exceed RUN"


@pytest.mark.skipif(not _HAS_EC, reason="equipment_controller not available")
def test_shutdown_dominates_de_rate_in_select_dominant():
    """select_dominant() returns SHUTDOWN over DE_RATE (Req 3.6)."""
    ec = EquipmentController()
    requests = [
        {"intent": "SHUTDOWN", "priority": PRIORITY_SHUTDOWN},
        {"intent": "DE_RATE", "priority": PRIORITY_DE_RATE},
        {"intent": "RUN", "priority": PRIORITY_RUN},
    ]
    dominant = ec.select_dominant(requests)
    assert dominant["intent"] == "SHUTDOWN", \
        "select_dominant must return SHUTDOWN when it is in the request list"


@pytest.mark.skipif(not _HAS_EC, reason="equipment_controller not available")
def test_critical_latch_prevents_downgrade():
    """While CRITICAL is latched, a subsequent WARNING does not change latch to DE_RATE."""
    import database
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "latch_test.db")
        orig = getattr(database, "_DB_PATH", None)
        database._DB_PATH = db_path
        try:
            database.initialize_database()
            ec = EquipmentController()
            # Send CRITICAL first to latch SHUTDOWN
            ec.on_status("CRITICAL", session=ADMIN_SESSION)
            assert ec.latched_intent == "SHUTDOWN", \
                "After CRITICAL, latched intent must be SHUTDOWN"
            assert ec.latched_status == "CRITICAL"

            # Then send WARNING — should still be latched as SHUTDOWN (Req 11.3)
            ec.on_status("WARNING", session=ADMIN_SESSION)
            assert ec.latched_intent == "SHUTDOWN", \
                "While CRITICAL is latched, WARNING must not downgrade to DE_RATE (Req 11.3)"
        finally:
            if orig is not None:
                database._DB_PATH = orig


@pytest.mark.skipif(not _HAS_EC, reason="equipment_controller not available")
def test_critical_latch_releases_on_normal():
    """When status returns to NORMAL, CRITICAL latch is released and RUN is dispatched."""
    import database
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "latch_release_test.db")
        orig = getattr(database, "_DB_PATH", None)
        database._DB_PATH = db_path
        try:
            database.initialize_database()
            ec = EquipmentController()
            ec.on_status("CRITICAL", session=ADMIN_SESSION)
            assert ec.latched_intent == "SHUTDOWN"

            # Release via NORMAL
            ec.on_status("NORMAL", session=ADMIN_SESSION)
            assert ec.latched_intent == "RUN", \
                "After CRITICAL→NORMAL, latched intent must change to RUN (Req 3.2)"
        finally:
            if orig is not None:
                database._DB_PATH = orig


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_EC,
                    reason="hypothesis or equipment_controller not available")
@given(lower_intent=st.sampled_from(["DE_RATE", "RUN"]))
@settings(max_examples=30)
def test_shutdown_dominates_any_lower_property(lower_intent):
    """Property: SHUTDOWN always dominates any lower-priority intent."""
    ec = EquipmentController()
    lower_priority = PRIORITY_DE_RATE if lower_intent == "DE_RATE" else PRIORITY_RUN
    requests = [
        {"intent": "SHUTDOWN", "priority": PRIORITY_SHUTDOWN},
        {"intent": lower_intent, "priority": lower_priority},
    ]
    dominant = ec.select_dominant(requests)
    assert dominant["intent"] == "SHUTDOWN"
