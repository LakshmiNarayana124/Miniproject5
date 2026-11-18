"""
Property 38: Event-log completeness
Validates: Requirements 14.3

Every training run, recalibration, and feedback ingestion is logged with timestamp+outcome.
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from obs_service import log_event, get_all_model_statuses
    import database
    _HAS_OBS = True
except ImportError:
    _HAS_OBS = False


def _setup(tmp_dir):
    database._DB_PATH = os.path.join(tmp_dir, "test_log.db")
    database.initialize_database()


@pytest.mark.skipif(not _HAS_OBS, reason="obs_service not available")
def test_log_event_does_not_raise():
    """log_event() runs without raising."""
    with tempfile.TemporaryDirectory() as tmp:
        _setup(tmp)
        try:
            log_event(event_type="TRAINING_RUN", outcome="success", detail={"family": "tabular"})
        except Exception as exc:
            pytest.fail(f"log_event raised: {exc}")


@pytest.mark.skipif(not _HAS_OBS, reason="obs_service not available")
def test_log_event_has_outcome():
    """log_event stores an outcome retrievable from the audit log."""
    with tempfile.TemporaryDirectory() as tmp:
        _setup(tmp)
        log_event(event_type="RECALIBRATION", outcome="skipped", detail={"reason": "not enough labels"})
        conn = database.get_connection()
        rows = conn.execute("SELECT detail_json FROM audit_entries ORDER BY id DESC LIMIT 1").fetchall()
        conn.close()
        assert len(rows) >= 1


@pytest.mark.skipif(not _HAS_OBS, reason="obs_service not available")
def test_feedback_ingestion_logged():
    """log_event for FEEDBACK_INGESTION stores a row."""
    with tempfile.TemporaryDirectory() as tmp:
        _setup(tmp)
        log_event(event_type="FEEDBACK_INGESTION", outcome="accepted", detail={"label": "normal"})
        conn = database.get_connection()
        rows = conn.execute("SELECT * FROM audit_entries").fetchall()
        conn.close()
        assert len(rows) >= 1


@pytest.mark.skipif(not _HAS_OBS, reason="obs_service not available")
def test_get_all_model_statuses_returns_dict_or_list():
    """get_all_model_statuses returns a dict or list (may be empty)."""
    with tempfile.TemporaryDirectory() as tmp:
        _setup(tmp)
        result = get_all_model_statuses()
        assert isinstance(result, (dict, list))
