"""
Property 7: Temperature feature correctness
Validates: Requirements 2.3

mean/min/max/rise_rate features are computed correctly.
"""
import math
import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from hypothesis import given, settings, assume
    from hypothesis import strategies as st
    _HAS_HYPOTHESIS = True
except ImportError:
    def given(*a, **kw): return lambda f: f
    def settings(*a, **kw): return lambda f: f
    def assume(cond): pass
    class st:  # noqa: N801
        @staticmethod
        def lists(*a, **kw): return []
        @staticmethod
        def floats(*a, **kw): return []
    _HAS_HYPOTHESIS = False

try:
    from feature_extractor import temperature_features
    _HAS_EXTRACTOR = True
except ImportError:
    _HAS_EXTRACTOR = False


def _ts():
    return datetime.now(timezone.utc).isoformat()


def _get(params, name):
    """Return the value of a named MonitoringParameter, or None if unavailable."""
    p = params.get(name)
    if p is None or not p.available:
        return None
    v = p.value
    return v if (v is not None and not math.isnan(v)) else None


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_mean_correct():
    """temperature_mean == 2.5 for [1.0, 2.0, 3.0, 4.0]."""
    params = temperature_features([1.0, 2.0, 3.0, 4.0], _ts(), "DS18B20")
    mean = _get(params, "temperature_mean")
    assert mean is not None, "temperature_mean should be available"
    assert math.isclose(mean, 2.5, rel_tol=1e-9), \
        f"expected mean=2.5, got {mean}"


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_min_max_correct():
    """temperature_min == 1.0 and temperature_max == 5.0 for [5.0, 1.0, 3.0]."""
    params = temperature_features([5.0, 1.0, 3.0], _ts(), "DS18B20")
    minimum = _get(params, "temperature_min")
    maximum = _get(params, "temperature_max")
    assert minimum is not None and maximum is not None, \
        "temperature_min and temperature_max should be available"
    assert math.isclose(minimum, 1.0, rel_tol=1e-9), \
        f"expected min=1.0, got {minimum}"
    assert math.isclose(maximum, 5.0, rel_tol=1e-9), \
        f"expected max=5.0, got {maximum}"


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_rise_rate_sign_increasing():
    """rise_rate > 0 for a strictly increasing sequence."""
    params = temperature_features([10.0, 20.0, 30.0, 40.0], _ts(), "DS18B20")
    rr = _get(params, "temperature_rise_rate")
    assert rr is not None, "temperature_rise_rate should be available"
    assert rr > 0, f"rise_rate should be positive for increasing sequence, got {rr}"


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_rise_rate_sign_decreasing():
    """rise_rate < 0 for a strictly decreasing sequence."""
    params = temperature_features([40.0, 30.0, 20.0, 10.0], _ts(), "DS18B20")
    rr = _get(params, "temperature_rise_rate")
    assert rr is not None, "temperature_rise_rate should be available"
    assert rr < 0, f"rise_rate should be negative for decreasing sequence, got {rr}"


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_mean_between_min_and_max_known():
    """Sanity check: mean falls between min and max for a known window."""
    params = temperature_features([0.0, 10.0, 20.0, 30.0], _ts(), "DS18B20")
    mean = _get(params, "temperature_mean")
    minimum = _get(params, "temperature_min")
    maximum = _get(params, "temperature_max")
    assert None not in (mean, minimum, maximum), "all features should be available"
    assert minimum <= mean <= maximum, \
        f"mean ({mean}) not in [{minimum}, {maximum}]"


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_EXTRACTOR,
                    reason="hypothesis or feature_extractor not available")
@given(
    values=st.lists(
        st.floats(min_value=-50.0, max_value=150.0, allow_nan=False, allow_infinity=False),
        min_size=4,
        max_size=50,
    )
)
@settings(max_examples=100)
def test_mean_between_min_and_max_property(values):
    """Property: temperature_mean is always between temperature_min and temperature_max."""
    params = temperature_features(values, _ts(), "DS18B20")
    mean = _get(params, "temperature_mean")
    minimum = _get(params, "temperature_min")
    maximum = _get(params, "temperature_max")
    # All features must be available for a non-empty window of finite values.
    assert mean is not None, "temperature_mean should be available for finite window"
    assert minimum is not None, "temperature_min should be available for finite window"
    assert maximum is not None, "temperature_max should be available for finite window"
    assert minimum <= mean + 1e-10, \
        f"mean ({mean}) below min ({minimum})"
    assert mean <= maximum + 1e-10, \
        f"mean ({mean}) above max ({maximum})"
