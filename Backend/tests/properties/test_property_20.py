"""
Property 20: Explorer feature-vector acceptance
Validates: Requirements 5.3

The explorer model accepts arrangement+readings and produces a non-empty
typed feature vector.
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
        def floats(**kw): return []
        @staticmethod
        def sampled_from(seq): return []
        @staticmethod
        def fixed_dictionaries(d): return []
    _HAS_HYPOTHESIS = False

try:
    from explorer_ml import classify, _feature_vector
    _HAS_EXPLORER = True
except ImportError:
    try:
        from explorer_ml import classify
        _HAS_EXPLORER = True
        _feature_vector = None
    except ImportError:
        _HAS_EXPLORER = False
        _feature_vector = None


# Minimal valid arrangement used across multiple tests.
_MINIMAL_ARRANGEMENT = [
    {"id": "raspberry-1", "type": "raspberry", "position": [0.0, 0.0, 0.0]},
    {"id": "adxl-1",      "type": "adxl",      "position": [1.0, 0.0, 0.0]},
]

# Minimal sensor readings keyed by component id.
_MINIMAL_READINGS = {
    "adxl-1": {"rms_x": 0.5, "rms_y": 0.3, "rms_z": 0.1},
}

VALID_LABELS = {"normal", "anomaly"}
KNOWN_COMP_TYPES = ["raspberry", "adxl", "acs", "ds18b20", "breadboard"]


@pytest.mark.skipif(not _HAS_EXPLORER, reason="explorer_ml not available")
def test_classify_returns_label_and_confidence():
    """classify returns a dict with 'label' (str) and 'confidence' in [0, 1]."""
    result = classify(_MINIMAL_ARRANGEMENT, _MINIMAL_READINGS)
    assert isinstance(result, dict), \
        f"classify must return a dict, got {type(result)}"
    assert "label" in result, \
        "classify result must contain 'label'"
    assert "confidence" in result, \
        "classify result must contain 'confidence'"
    assert isinstance(result["label"], str), \
        f"'label' must be a string, got {type(result['label'])}"
    confidence = result["confidence"]
    assert isinstance(confidence, (int, float)), \
        f"'confidence' must be numeric, got {type(confidence)}"
    assert 0.0 <= float(confidence) <= 1.0, \
        f"'confidence' must be in [0, 1], got {confidence}"


@pytest.mark.skipif(not _HAS_EXPLORER, reason="explorer_ml not available")
def test_classify_label_is_known_value():
    """The returned label is one of the known class names."""
    result = classify(_MINIMAL_ARRANGEMENT, _MINIMAL_READINGS)
    assert result["label"] in VALID_LABELS, \
        f"label must be one of {VALID_LABELS}, got {result['label']!r}"


@pytest.mark.skipif(not _HAS_EXPLORER, reason="explorer_ml not available")
def test_classify_has_model_version():
    """classify result must include 'model_version' (Req 5.2)."""
    result = classify(_MINIMAL_ARRANGEMENT, _MINIMAL_READINGS)
    assert "model_version" in result, \
        "classify result must contain 'model_version'"
    assert result["model_version"] is not None, \
        "'model_version' must not be None"


@pytest.mark.skipif(not _HAS_EXPLORER, reason="explorer_ml not available")
def test_feature_vector_non_empty():
    """The internal feature vector built from arrangement + readings is non-empty."""
    if _feature_vector is None:
        pytest.skip("_feature_vector not importable from explorer_ml")
    fv = _feature_vector(_MINIMAL_ARRANGEMENT, _MINIMAL_READINGS)
    assert isinstance(fv, dict), \
        f"_feature_vector must return a dict, got {type(fv)}"
    assert len(fv) > 0, \
        "feature vector must be non-empty for a non-trivial arrangement+readings"


@pytest.mark.skipif(not _HAS_EXPLORER, reason="explorer_ml not available")
def test_classify_empty_arrangement_no_crash():
    """classify with an empty arrangement does not raise and returns valid output."""
    result = classify([], {})
    assert "label" in result
    assert "confidence" in result
    assert 0.0 <= float(result["confidence"]) <= 1.0


@pytest.mark.skipif(not _HAS_EXPLORER, reason="explorer_ml not available")
def test_classify_readings_with_extreme_values():
    """Extreme sensor readings (e.g. 1e6) do not cause an exception."""
    readings = {
        "adxl-1": {"rms_x": 1e6, "rms_y": -1e6, "rms_z": 0.0},
    }
    result = classify(_MINIMAL_ARRANGEMENT, readings)
    assert "label" in result
    assert 0.0 <= float(result["confidence"]) <= 1.0


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_EXPLORER,
                    reason="hypothesis or explorer_ml not available")
@given(
    n_components=st.integers(min_value=1, max_value=6),
    comp_type=st.sampled_from(KNOWN_COMP_TYPES),
    reading_val=st.floats(min_value=-100.0, max_value=100.0,
                          allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_classify_feature_vector_acceptance_property(n_components, comp_type, reading_val):
    """Property: classify always produces a valid label and confidence in [0,1]."""
    arrangement = [
        {"id": f"{comp_type}-{i}", "type": comp_type,
         "position": [float(i), 0.0, 0.0]}
        for i in range(n_components)
    ]
    readings = {
        f"{comp_type}-{i}": {"sensor_val": reading_val}
        for i in range(n_components)
    }
    result = classify(arrangement, readings)

    assert "label" in result, "result must have 'label'"
    assert "confidence" in result, "result must have 'confidence'"
    assert isinstance(result["label"], str), \
        f"'label' must be a string, got {type(result['label'])}"
    confidence = float(result["confidence"])
    assert 0.0 <= confidence <= 1.0, \
        f"'confidence' ({confidence}) must be in [0, 1]"
