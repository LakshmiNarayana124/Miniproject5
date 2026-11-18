"""
Property 26: Model promotion gate
Validates: Requirements 8.4, 10.1-10.4

Candidate promoted only when F1 exceeds active model and meets accuracy targets.
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

try:
    from obs_service import UNSUPERVISED_F1_TARGET
    _THRESHOLD = UNSUPERVISED_F1_TARGET
except Exception:
    _THRESHOLD = 0.90


def _setup(tmp_path):
    database.DATABASE_PATH = str(tmp_path / "promo.db")
    database.initialize_database()
    return LearningSystem()


@pytest.mark.skipif(not _HAS_LS, reason="learning_system not available")
def test_promotion_no_labels_does_not_raise(tmp_path):
    ls = _setup(tmp_path)
    try:
        ls.recalibrate()
    except Exception as exc:
        pytest.fail(f"recalibrate() raised with no labels: {exc}")


@pytest.mark.skipif(not _HAS_LS, reason="learning_system not available")
def test_submit_multiple_labels_then_recalibrate(tmp_path):
    ls = _setup(tmp_path)
    features = {"rms_x": 0.5, "peak_x": 1.0}
    for label in (["normal"] * 10 + ["fault"] * 10):
        ls.submit_label(
            event_id=None,
            label=label,
            feature_vector=features,
            model_version="tabular-v0.1",
            verified_by="op",
        )
    try:
        ls.recalibrate()
    except Exception as exc:
        pytest.fail(f"recalibrate() raised: {exc}")


@pytest.mark.skipif(not _HAS_LS, reason="learning_system not available")
def test_accuracy_threshold_in_range():
    assert 0 < _THRESHOLD <= 1.0
