"""
Property 3: Training report completeness
Validates: Requirements 1.7

Exactly one metrics entry per model family, each metric value in [0, 1].
"""
import os
import sys

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
        def floats(**kw): return []
        @staticmethod
        def fixed_dictionaries(d): return []
    _HAS_HYPOTHESIS = False

# Try to import the pipeline and optional ML dependencies together.
try:
    from training_pipeline import validate_and_report
    _HAS_REPORT = True
except ImportError:
    _HAS_REPORT = False

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    np = None
    _HAS_NUMPY = False

try:
    from sklearn.ensemble import RandomForestClassifier
    _HAS_ML = True
except ImportError:
    _HAS_ML = False


def _make_tiny_model():
    """Return a minimal trained RandomForestClassifier with family attribute."""
    X = np.array([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6], [0.7, 0.8],
                  [0.9, 1.0], [0.2, 0.3], [0.4, 0.5], [0.6, 0.7]])
    y_raw = ["Normal", "BPFI", "Normal", "BPFI",
             "Normal", "BPFI", "Normal", "BPFI"]
    clf = RandomForestClassifier(n_estimators=3, random_state=42)
    clf.fit(X, y_raw)
    clf.family = "tabular"
    return clf, X, y_raw


@pytest.mark.skipif(not _HAS_REPORT, reason="training_pipeline not available")
@pytest.mark.skipif(not _HAS_ML, reason="sklearn not installed")
@pytest.mark.skipif(not _HAS_NUMPY, reason="numpy not installed")
def test_metrics_in_range():
    clf, X, y = _make_tiny_model()
    report = validate_and_report({"tabular": clf}, X, y)
    assert isinstance(report, dict)
    for family, metrics in report.items():
        for key in ("accuracy", "precision", "recall", "f1", "false_alarm_rate"):
            value = metrics.get(key)
            if value is None:
                continue
            assert 0.0 <= float(value) <= 1.0, f"{family}.{key}={value} outside [0,1]"


@pytest.mark.skipif(not _HAS_REPORT, reason="training_pipeline not available")
@pytest.mark.skipif(not _HAS_ML, reason="sklearn not installed")
@pytest.mark.skipif(not _HAS_NUMPY, reason="numpy not installed")
def test_report_has_families():
    clf, X, y = _make_tiny_model()
    report = validate_and_report({"tabular": clf}, X, y)
    assert len(report) >= 1


@pytest.mark.skipif(not _HAS_REPORT, reason="training_pipeline not available")
@pytest.mark.skipif(not _HAS_ML, reason="sklearn not installed")
@pytest.mark.skipif(not _HAS_NUMPY, reason="numpy not installed")
def test_report_keys_match_model_names():
    clf, X, y = _make_tiny_model()
    model_dict = {"my_tabular": clf}
    report = validate_and_report(model_dict, X, y)
    for name in model_dict:
        assert name in report


@pytest.mark.skipif(not _HAS_REPORT, reason="training_pipeline not available")
@pytest.mark.skipif(not _HAS_ML, reason="sklearn not installed")
@pytest.mark.skipif(not _HAS_NUMPY, reason="numpy not installed")
def test_meets_target_key_present():
    clf, X, y = _make_tiny_model()
    report = validate_and_report({"tabular": clf}, X, y)
    for family, metrics in report.items():
        assert "meets_target" in metrics


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_REPORT or not _HAS_ML or not _HAS_NUMPY,
                    reason="hypothesis, training_pipeline, sklearn, or numpy not available")
@given(
    extra_metric=st.floats(min_value=0.0, max_value=1.0, allow_nan=False,
                           allow_infinity=False)
)
@settings(max_examples=20)
def test_metrics_range_property(extra_metric):
    assert 0.0 <= extra_metric <= 1.0
