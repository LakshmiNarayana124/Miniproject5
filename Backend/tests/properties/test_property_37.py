"""
Property 37: Control-signal authorization gate.
Validates: Req 13.3, 13.5

Unauthorized roles are rejected; authorized roles succeed.
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
    from equipment_controller import EquipmentController, PermissionDenied, ACTUATION_ROLES
    _HAS_EC = True
except ImportError:
    try:
        from equipment_controller import EquipmentController, PermissionDenied
        ACTUATION_ROLES = frozenset({"ADMIN", "MAINTENANCE_ENGINEER"})
        _HAS_EC = True
    except ImportError:
        _HAS_EC = False
        PermissionDenied = Exception


def _make_controller(tmp_dir, suffix="auth"):
    """Return an EquipmentController backed by a temp database."""
    import database
    from pathlib import Path
    database.DATABASE_PATH = Path(os.path.join(tmp_dir, f"{suffix}.db"))
    database.initialize_database()
    return EquipmentController()


@pytest.mark.skipif(not _HAS_EC, reason="equipment_controller not available")
def test_operator_cannot_dispatch_shutdown():
    """An OPERATOR session must not be allowed to issue SHUTDOWN (Req 13.3)."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = database.DATABASE_PATH
        try:
            ec = _make_controller(tmp, "operator_reject")
            operator_session = {"role": "OPERATOR", "username": "op_user"}

            with pytest.raises(PermissionDenied):
                ec.dispatch(
                    intent="SHUTDOWN",
                    status="CRITICAL",
                    session=operator_session,
                )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_EC, reason="equipment_controller not available")
def test_admin_can_dispatch():
    """An ADMIN session must be allowed to dispatch SHUTDOWN (Req 13.3)."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = database.DATABASE_PATH
        try:
            ec = _make_controller(tmp, "admin_ok")
            admin_session = {"role": "ADMIN", "username": "admin_user"}

            result = ec.dispatch(
                intent="SHUTDOWN",
                status="CRITICAL",
                session=admin_session,
            )
            assert result["intent"] == "SHUTDOWN", (
                "ADMIN must be able to dispatch SHUTDOWN"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_EC, reason="equipment_controller not available")
def test_maintenance_engineer_can_dispatch():
    """A MAINTENANCE_ENGINEER session must be allowed to dispatch SHUTDOWN."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = database.DATABASE_PATH
        try:
            ec = _make_controller(tmp, "me_ok")
            me_session = {"role": "MAINTENANCE_ENGINEER", "username": "eng_user"}

            result = ec.dispatch(
                intent="SHUTDOWN",
                status="CRITICAL",
                session=me_session,
            )
            assert result["intent"] == "SHUTDOWN", (
                "MAINTENANCE_ENGINEER must be able to dispatch SHUTDOWN"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_EC, reason="equipment_controller not available")
def test_no_session_cannot_dispatch():
    """A None session must be rejected for SHUTDOWN (Req 13.3)."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = database.DATABASE_PATH
        try:
            ec = _make_controller(tmp, "nosession_reject")

            with pytest.raises(PermissionDenied):
                ec.dispatch(
                    intent="SHUTDOWN",
                    status="CRITICAL",
                    session=None,
                )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_EC, reason="equipment_controller not available")
def test_demo_role_cannot_dispatch_de_rate():
    """A 'demo' role session must not be allowed to issue DE_RATE (Req 13.5)."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = database.DATABASE_PATH
        try:
            ec = _make_controller(tmp, "demo_reject")
            demo_session = {"role": "demo", "username": "demo_user"}

            with pytest.raises(PermissionDenied):
                ec.dispatch(
                    intent="DE_RATE",
                    status="WARNING",
                    session=demo_session,
                )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_EC,
                    reason="hypothesis or equipment_controller not available")
@given(bad_role=st.sampled_from(["OPERATOR", "demo"]))
@settings(max_examples=100)
def test_property_unauthorized_roles_always_rejected(bad_role):
    """Property: OPERATOR and demo roles always raise PermissionDenied for SHUTDOWN/DE_RATE."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = database.DATABASE_PATH
        try:
            from pathlib import Path
            database.DATABASE_PATH = Path(
                os.path.join(tmp, f"prop_{bad_role}.db")
            )
            database.initialize_database()
            ec = EquipmentController()

            session = {"role": bad_role, "username": f"{bad_role}_user"}

            for intent in ("SHUTDOWN", "DE_RATE"):
                with pytest.raises(PermissionDenied):
                    ec.dispatch(
                        intent=intent,
                        status="CRITICAL",
                        session=session,
                    )
        finally:
            database.DATABASE_PATH = orig
