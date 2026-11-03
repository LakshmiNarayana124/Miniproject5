"""
Property 19: Explorer model classification validity
Validates: Requirements 5.2

Assert that the explorer classify() function returns a valid label and
confidence within [0, 1].
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
        def integers(**kw): return []
        @staticmethod
        def sampled_from(seq): return []
    _HAS_HYPOTHESIS = False

try:
    from explorer_ml import classify
    _HAS_EXPLORER = True
except ImportError:
    _HAS_EXPLORER = False


VALID_LABELS = {"normal", "anomaly"}


@pytest.mark.skipif(not _HAS_EXPLORER, reason="explorer_ml not available")
def test_classify_empty_arrangement():
    """classify with empty arrangement returns a valid label and confidence."""
    result = classify([], {})
    assert "label" in result
    assert "confidence" in result
    assert 0.0 <= result["confidence"] <= 1.0


@pytest.mark.skipif(not _HAS_EXPLORER, reason="explorer_ml not available")
def test_classify_typical_arrangement():
    """classify with a typical arrangement returns a valid label and confidence."""
    arrangement = [
        {"id": "raspberry-1", "type": "raspberry", "position": [0, 0, 0]},
        {"id": "adxl-1", "type": "adxl", "position": [1, 0, 0]},
        {"id": "acs-1", "type": "acs", "position": [2, 0, 0]},
    ]
    result = classify(arrangement, {})
    assert result["label"] in VALID_LABELS, \
        f"label must be one of {VALID_LABELS}, got {result['label']!r}"
    assert 0.0 <= result["confidence"] <= 1.0
    assert "model_version" in result


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_EXPLORER,
                    reason="hypothesis or explorer_ml not available")
@given(
    n_components=st.integers(min_value=0, max_value=8),
    comp_type=st.sampled_from(["raspberry", "adxl", "acs", "ds18b20", "breadboard"]),
)
@settings(max_examples=100)
def test_classify_property(n_components, comp_type):
    """Property: classify always returns a valid label and confidence in [0, 1]."""
    arrangement = [
        {"id": f"{comp_type}-{i}", "type": comp_type, "position": [float(i), 0, 0]}
        for i in range(n_components)
    ]
    result = classify(arrangement, {})

    assert "label" in result, "result must have 'label'"
    assert "confidence" in result, "result must have 'confidence'"
    assert 0.0 <= result["confidence"] <= 1.0, \
        f"confidence ({result['confidence']}) must be in [0, 1]"
