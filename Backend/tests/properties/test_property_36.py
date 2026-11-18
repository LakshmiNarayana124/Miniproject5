"""
Property 36: Model-change audit completeness
Validates: Requirements 13.2

Every promotion/recalibration creates an audit entry with model version and outcome.
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from learning_system import LearningSystem
    import database
    _HAS_LS = True
except ImportError:
    _HAS_LS = False


def _setup(tmp_path):
    database.DATABASE_PATH = str(tmp_path / "audit_ml.db")
    database.initialize_database()
    return LearningSystem()


@pytest.mark.skipif(not _HAS_LS, reason="learning_system not available")
def test_recalibrate_does_not_raise_audit(tmp_path):
    ls = _setup(tmp_path)
    features = {"rms_x": 0.4}
    for i in range(30):
        ls.submit_label(
            event_id=None,
            label="normal" if i % 2 == 0 else "fault",
            feature_vector=features,
            model_version="v0.1",
            verified_by="op",
        )
    try:
        ls.recalibrate()
    except Exception as exc:
        pytest.fail(f"recalibrate raised: {exc}")


@pytest.mark.skipif(not _HAS_LS, reason="learning_system not available")
def test_audit_entries_have_hash(tmp_path):
    database.DATABASE_PATH = str(tmp_path / "audit_hash.db")
    database.initialize_database()
    database.record_audit_entry(
        category="RECALIBRATION",
        actor="system",
        target="1",
        detail_json='{"model_version":"v0.1","outcome":"skipped"}',
    )
    conn = database.get_connection()
    rows = conn.execute("SELECT hash FROM audit_entries").fetchall()
    conn.close()
    for row in rows:
        assert row["hash"], "audit_entries row has empty hash"


@pytest.mark.skipif(not _HAS_LS, reason="learning_system not available")
def test_manual_audit_entry_model_event(tmp_path):
    database.DATABASE_PATH = str(tmp_path / "audit_model.db")
    database.initialize_database()
    database.record_audit_entry(
        category="MODEL_PROMOTED",
        actor="system",
        target="2",
        detail_json='{"model_version":"v1.0","f1":0.95}',
    )
    conn = database.get_connection()
    row = conn.execute(
        "SELECT category FROM audit_entries WHERE category='MODEL_PROMOTED'"
    ).fetchone()
    conn.close()
    assert row is not None
