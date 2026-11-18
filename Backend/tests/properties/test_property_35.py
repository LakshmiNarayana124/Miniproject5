"""
Property 35: Control-signal audit completeness.
Validates: Req 13.1

Every dispatch creates an immutable audit entry with required fields.
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
    import database as _db_module
    _HAS_DB = True
except ImportError:
    _HAS_DB = False

ADMIN_SESSION = {"role": "ADMIN", "username": "test_admin"}


def _setup_db(tmp_dir, suffix="audit"):
    """Point database module at a fresh temp DB and return the orig path."""
    import database
    from pathlib import Path
    orig = database.DATABASE_PATH
    database.DATABASE_PATH = Path(os.path.join(tmp_dir, f"{suffix}.db"))
    database.initialize_database()
    return orig


def _query_audit_entries(category_fragment=None):
    """Return all audit_entries rows, optionally filtered by category substring."""
    import database
    conn = database.get_connection()
    try:
        if category_fragment:
            rows = conn.execute(
                "SELECT * FROM audit_entries WHERE category LIKE ?",
                (f"%{category_fragment}%",),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM audit_entries").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@pytest.mark.skipif(not _HAS_EC or not _HAS_DB,
                    reason="equipment_controller or database not available")
def test_audit_entry_created_on_dispatch():
    """Dispatching a signal must create at least one audit_entries row (Req 13.1)."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = _setup_db(tmp)
        try:
            ec = EquipmentController()
            ec.dispatch(
                intent="SHUTDOWN",
                status="CRITICAL",
                session=ADMIN_SESSION,
            )

            rows = _query_audit_entries()
            assert len(rows) >= 1, (
                "At least one audit entry must be created after a dispatch (Req 13.1)"
            )

            # At least one row should have a category related to control dispatch.
            control_rows = [
                r for r in rows
                if "control" in str(r.get("category", "")).lower()
            ]
            assert len(control_rows) >= 1, (
                "An audit entry with a 'control'-related category must exist after dispatch"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_EC or not _HAS_DB,
                    reason="equipment_controller or database not available")
def test_audit_entry_has_hash():
    """Every audit entry created by a dispatch must have a non-empty hash field."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = _setup_db(tmp, "hash_test")
        try:
            ec = EquipmentController()
            ec.dispatch(
                intent="DE_RATE",
                status="WARNING",
                session=ADMIN_SESSION,
            )

            rows = _query_audit_entries()
            assert rows, "Expected at least one audit entry"

            for row in rows:
                hash_val = row.get("hash", "")
                assert hash_val and str(hash_val).strip(), (
                    f"Audit entry id={row.get('id')} has an empty hash field"
                )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_EC or not _HAS_DB,
                    reason="equipment_controller or database not available")
def test_audit_entry_required_fields():
    """Every audit entry must contain timestamp, category, detail_json, and hash."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = _setup_db(tmp, "fields_test")
        try:
            ec = EquipmentController()
            ec.dispatch(
                intent="SHUTDOWN",
                status="CRITICAL",
                session=ADMIN_SESSION,
            )

            rows = _query_audit_entries()
            assert rows, "Expected at least one audit entry after dispatch"

            required_fields = {"timestamp", "category", "detail_json", "hash"}
            for row in rows:
                for field in required_fields:
                    assert row.get(field) is not None and str(row[field]).strip(), (
                        f"Audit entry id={row.get('id')} missing required field '{field}'"
                    )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_EC or not _HAS_DB,
                    reason="equipment_controller or database not available")
def test_multiple_dispatches_create_multiple_entries():
    """Each dispatch must create its own audit entry (entries are not de-duplicated)."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = _setup_db(tmp, "multi_test")
        try:
            ec = EquipmentController()
            ec.dispatch(
                intent="SHUTDOWN",
                status="CRITICAL",
                session=ADMIN_SESSION,
            )
            # Fresh controller to avoid CRITICAL latch.
            database.DATABASE_PATH = database.DATABASE_PATH  # same path
            ec2 = EquipmentController()
            ec2.dispatch(
                intent="DE_RATE",
                status="WARNING",
                session=ADMIN_SESSION,
            )

            rows = _query_audit_entries()
            assert len(rows) >= 2, (
                "Each dispatch must produce at least one additional audit entry"
            )
        finally:
            database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_EC or not _HAS_DB,
                    reason="hypothesis, equipment_controller, or database not available")
@given(intent=st.sampled_from(["SHUTDOWN", "DE_RATE"]))
@settings(max_examples=100)
def test_property_every_dispatch_audited(intent):
    """Property: every authorized dispatch produces at least one audit entry."""
    with tempfile.TemporaryDirectory() as tmp:
        import database
        orig = database.DATABASE_PATH
        try:
            from pathlib import Path
            database.DATABASE_PATH = Path(
                os.path.join(tmp, f"prop_{intent}.db")
            )
            database.initialize_database()
            ec = EquipmentController()

            before = len(_query_audit_entries())
            ec.dispatch(
                intent=intent,
                status="CRITICAL" if intent == "SHUTDOWN" else "WARNING",
                session=ADMIN_SESSION,
            )
            after = len(_query_audit_entries())

            assert after > before, (
                f"Dispatch of {intent} must add at least one audit entry"
            )
        finally:
            database.DATABASE_PATH = orig
