"""
Property 8: Current feature correctness
Validates: Requirements 2.4

Per-phase rms and mean satisfy statistical definitions.
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
    from feature_extractor import current_features
    _HAS_EXTRACTOR = True
except ImportError:
    _HAS_EXTRACTOR = False


def _ts():
    return datetime.now(timezone.utc).isoformat()


def _extract(window):
    """Call current_features with the same window on all three phases."""
    return current_features(
        window_a=window,
        window_b=window,
        window_c=window,
        ts=_ts(),
        source="ACS712",
    )


def _get(params, name):
    """Return the float value of a MonitoringParameter, or None if unavailable."""
    p = params.get(name)
    if p is None or not p.available:
        return None
    v = p.value
    return v if (v is not None and not math.isnan(v)) else None


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_rms_non_negative():
    """current_rms_* must be non-negative for any finite window."""
    window = [0.1, -0.5, 0.3, -0.8, 0.6]
    params = _extract(window)
    for phase in ("a", "b", "c"):
        rms = _get(params, f"current_rms_{phase}")
        if rms is not None:
            assert rms >= 0.0, f"current_rms_{phase} must be non-negative, got {rms}"


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_mean_matches_arithmetic():
    """current_mean_* == 2.0 for a constant window [2.0, 2.0, 2.0, 2.0]."""
    window = [2.0, 2.0, 2.0, 2.0]
    params = _extract(window)
    for phase in ("a", "b", "c"):
        mean = _get(params, f"current_mean_{phase}")
        assert mean is not None, f"current_mean_{phase} should be available"
        assert math.isclose(mean, 2.0, rel_tol=1e-9), \
            f"expected current_mean_{phase}=2.0, got {mean}"


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_rms_geq_abs_mean():
    """rms >= abs(mean) for any real signal (Cauchy-Schwarz inequality)."""
    window = [1.0, 2.0, 3.0, -1.0, 0.5]
    params = _extract(window)
    for phase in ("a", "b", "c"):
        rms = _get(params, f"current_rms_{phase}")
        mean = _get(params, f"current_mean_{phase}")
        if rms is not None and mean is not None:
            assert rms >= abs(mean) - 1e-10, \
                f"rms ({rms}) must be >= abs(mean) ({abs(mean)}) for phase {phase}"


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_rms_known_value():
    """RMS of [3.0, -4.0] == sqrt((9+16)/2) == sqrt(12.5)."""
    window = [3.0, -4.0]
    params = current_features(window, window, window, _ts(), "ACS712")
    expected = math.sqrt(12.5)
    for phase in ("a", "b", "c"):
        rms = _get(params, f"current_rms_{phase}")
        assert rms is not None, f"current_rms_{phase} should be available"
        assert math.isclose(rms, expected, rel_tol=1e-9), \
            f"expected current_rms_{phase}={expected}, got {rms}"


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_EXTRACTOR,
                    reason="hypothesis or feature_extractor not available")
@given(
    values=st.lists(
        st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        min_size=4,
        max_size=50,
    )
)
@settings(max_examples=100)
def test_rms_non_negative_property(values):
    """Property: all available current_rms_* values are non-negative."""
    params = _extract(values)
    for phase in ("a", "b", "c"):
        rms = _get(params, f"current_rms_{phase}")
        if rms is not None:
            assert rms >= 0.0, \
                f"current_rms_{phase} must be non-negative, got {rms}"
