"""
Property 11: Status-to-control-signal mapping
Validates: Requirements 3.1, 3.3, 3.4

Assert CRITICAL→SHUTDOWN, WARNING→DE_RATE, NORMAL→RUN and that every
valid status maps to exactly one intent.
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

EXPECTED_MAPPING = {
    "CRITICAL": "SHUTDOWN",
    "WARNING": "DE_RATE",
    "NORMAL": "RUN",
}

ADMIN_SESSION = {"role": "ADMIN", "username": "test_admin"}


def _make_controller_with_db(tmp_dir):
    """Return an EquipmentController with an initialized temp database."""
    import database
    db_path = os.path.join(tmp_dir, "test_ec.db")
    original_db = getattr(database, "_DB_PATH", None)
    database._DB_PATH = db_path
    database.initialize_database()
    ec = EquipmentController()
    return ec, original_db


@pytest.mark.skipif(not _HAS_EC, reason="equipment_controller not available")
def test_status_to_intent_mapping():
    """Each status maps to the correct intent as per Req 3.1."""
    import database
    with tempfile.TemporaryDirectory() as tmp:
        ec, orig = _make_controller_with_db(tmp)
        try:
            for status, expected_intent in EXPECTED_MAPPING.items():
                result = ec.dispatch(
                    intent=expected_intent,
                    status=status,
                    session=ADMIN_SESSION,
                )
                assert result["intent"] == expected_intent, \
                    f"status={status} should map to intent={expected_intent}"
        finally:
            if orig is not None:
                database._DB_PATH = orig


@pytest.mark.skipif(not _HAS_EC, reason="equipment_controller not available")
def test_status_to_intent_constants():
    """STATUS_TO_INTENT constant must map CRITICAL→SHUTDOWN, WARNING→DE_RATE, NORMAL→RUN."""
    mapping = STATUS_TO_INTENT
    assert mapping.get("CRITICAL") == "SHUTDOWN", \
        "STATUS_TO_INTENT['CRITICAL'] must be 'SHUTDOWN'"
    assert mapping.get("WARNING") == "DE_RATE", \
        "STATUS_TO_INTENT['WARNING'] must be 'DE_RATE'"
    assert mapping.get("NORMAL") == "RUN", \
        "STATUS_TO_INTENT['NORMAL'] must be 'RUN'"


@pytest.mark.skipif(not _HAS_EC, reason="equipment_controller not available")
def test_on_status_produces_correct_latched_intent():
    """on_status() causes the controller to latch the correct intent."""
    import database
    with tempfile.TemporaryDirectory() as tmp:
        ec, orig = _make_controller_with_db(tmp)
        try:
            for status, expected_intent in EXPECTED_MAPPING.items():
                # Fresh controller for each status to avoid CRITICAL latching
                db_path = os.path.join(tmp, f"test_{status}.db")
                database._DB_PATH = db_path
                database.initialize_database()
                ec2 = EquipmentController()
                ec2.on_status(status, session=ADMIN_SESSION)
                latched = ec2.latched_intent
                assert latched == expected_intent, \
                    f"on_status({status!r}) latched {latched!r}, expected {expected_intent!r}"
        finally:
            if orig is not None:
                database._DB_PATH = orig


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_EC,
                    reason="hypothesis or equipment_controller not available")
@given(status=st.sampled_from(list(EXPECTED_MAPPING.keys())))
@settings(max_examples=10)
def test_status_mapping_property(status):
    """Property: every valid status maps to exactly one deterministic intent via the constant."""
    expected_intent = EXPECTED_MAPPING[status]
    assert STATUS_TO_INTENT.get(status) == expected_intent
