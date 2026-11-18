"""
Property 25: Operator label ingestion and storage
Validates: Requirements 8.1, 8.2

Submitted labels are stored with feature vector, model version, and timestamp.
"""
import os
import sys
import json
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from learning_system import LearningSystem
    import database
    _HAS_LS = True
except ImportError:
    _HAS_LS = False

_FEATURES = {"rms_x": 0.5, "peak_x": 1.0, "mean_temp": 55.0}
_MODEL_VER = "tabular-v1.0"


def _setup(tmp_path):
    database.DATABASE_PATH = str(tmp_path / "ls.db")
    database.initialize_database()
    return LearningSystem()


@pytest.mark.skipif(not _HAS_LS, reason="learning_system not available")
def test_label_stored(tmp_path):
    ls = _setup(tmp_path)
    ls.submit_label(
        event_id=None,
        label="normal",
        feature_vector=_FEATURES,
        model_version=_MODEL_VER,
        verified_by="operator1",
    )
    conn = database.get_connection()
    rows = conn.execute("SELECT * FROM verified_labels").fetchall()
    conn.close()
    assert len(rows) >= 1


@pytest.mark.skipif(not _HAS_LS, reason="learning_system not available")
def test_label_has_model_version(tmp_path):
    ls = _setup(tmp_path)
    ls.submit_label(
        event_id=None,
        label="fault",
        feature_vector=_FEATURES,
        model_version=_MODEL_VER,
        verified_by="operator1",
    )
    conn = database.get_connection()
    row = conn.execute("SELECT * FROM verified_labels ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    assert row["model_version"], "model_version is empty"


@pytest.mark.skipif(not _HAS_LS, reason="learning_system not available")
def test_label_has_timestamp(tmp_path):
    ls = _setup(tmp_path)
    ls.submit_label(
        event_id=None,
        label="normal",
        feature_vector=_FEATURES,
        model_version=_MODEL_VER,
        verified_by="operator1",
    )
    conn = database.get_connection()
    row = conn.execute("SELECT * FROM verified_labels ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    assert row["verified_at"], "verified_at is empty"


@pytest.mark.skipif(not _HAS_LS, reason="learning_system not available")
def test_label_feature_vector_stored(tmp_path):
    ls = _setup(tmp_path)
    ls.submit_label(
        event_id=None,
        label="normal",
        feature_vector=_FEATURES,
        model_version=_MODEL_VER,
        verified_by="operator1",
    )
    conn = database.get_connection()
    row = conn.execute("SELECT * FROM verified_labels ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    stored = json.loads(row["feature_vector_json"])
    assert stored.get("rms_x") == pytest.approx(0.5)
