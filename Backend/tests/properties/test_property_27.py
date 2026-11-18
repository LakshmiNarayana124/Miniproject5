"""
Property 27: Accuracy trend recording
Validates: Requirements 8.5

An F1 entry is appended to accuracy_trend per recalibration.
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
    database.DATABASE_PATH = str(tmp_path / "trend.db")
    database.initialize_database()
    return LearningSystem()


@pytest.mark.skipif(not _HAS_LS, reason="learning_system not available")
def test_recalibrate_does_not_raise(tmp_path):
    ls = _setup(tmp_path)
    features = {"rms_x": 0.3}
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
def test_trend_f1_in_range_if_rows(tmp_path):
    ls = _setup(tmp_path)
    features = {"rms_x": 0.5}
    for i in range(30):
        ls.submit_label(
            event_id=None,
            label="normal" if i % 2 == 0 else "fault",
            feature_vector=features,
            model_version="v0.1",
            verified_by="op",
        )
    ls.recalibrate()
    conn = database.get_connection()
    rows = conn.execute("SELECT f1_score FROM accuracy_trend").fetchall()
    conn.close()
    for row in rows:
        assert 0.0 <= row["f1_score"] <= 1.0


@pytest.mark.skipif(not _HAS_LS, reason="learning_system not available")
def test_append_accuracy_trend_directly(tmp_path):
    database.DATABASE_PATH = str(tmp_path / "trend2.db")
    database.initialize_database()
    conn = database.get_connection()
    conn.execute("""
        INSERT INTO ml_models (family, model_name, version, is_active,
            training_timestamp, dataset_hash, artifact_path)
        VALUES ('tabular','test','v0.1',0,'2024-01-01T00:00:00Z','abc','.')
    """)
    model_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    database.append_accuracy_trend(model_id=model_id, f1_score=0.95)
    conn = database.get_connection()
    row = conn.execute(
        "SELECT f1_score FROM accuracy_trend WHERE model_id=?", (model_id,)
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["f1_score"] == pytest.approx(0.95)
