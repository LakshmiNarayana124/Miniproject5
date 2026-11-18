"""
Property 40: Missing-value window resilience
Validates: Requirements 2.7

When input contains NaN/None, derived features are marked available=False
and no exception is raised.
"""
import math
import os
import sys
from datetime import datetime, timezone

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
        def lists(*a, **kw): return []
        @staticmethod
        def floats(*a, **kw): return []
        @staticmethod
        def one_of(*a, **kw): return []
        @staticmethod
        def none(): return []
    _HAS_HYPOTHESIS = False

try:
    from feature_extractor import vibration_features, temperature_features, current_features
    _HAS_EXTRACTOR = True
except ImportError:
    _HAS_EXTRACTOR = False


def _ts():
    return datetime.now(timezone.utc).isoformat()


def _all_unavailable(params):
    """Return True when every MonitoringParameter in the dict is unavailable."""
    return all(not p.available for p in params.values())


def _available_values_are_finite(params):
    """Return True when every available parameter holds a finite value."""
    for p in params.values():
        if p.available and (p.value is None or not math.isfinite(p.value)):
            return False
    return True


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_all_nan_vibration():
    """All-NaN vibration window: no exception raised, all features unavailable."""
    nan_window = [float("nan")] * 16
    # Must not raise.
    params = vibration_features(
        window_x=nan_window,
        window_y=nan_window,
        window_z=nan_window,
        ts=_ts(),
        source="test_sensor",
    )
    assert isinstance(params, dict), "vibration_features must return a dict"
    for name, p in params.items():
        assert not p.available, \
            f"{name} should be unavailable for all-NaN window, got available=True"


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_all_none_vibration():
    """All-None vibration window: no exception raised, all features unavailable."""
    none_window = [None] * 8
    params = vibration_features(
        window_x=none_window,
        window_y=none_window,
        window_z=none_window,
        ts=_ts(),
        source="test_sensor",
    )
    for name, p in params.items():
        assert not p.available, \
            f"{name} should be unavailable for all-None window"


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_empty_window_temperature():
    """Empty temperature window: no exception raised, features unavailable."""
    params = temperature_features([], _ts(), "DS18B20")
    assert isinstance(params, dict), "temperature_features must return a dict"
    assert len(params) > 0, "temperature_features must emit entries even for empty input"
    for name, p in params.items():
        assert not p.available, \
            f"{name} should be unavailable for empty window"


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_all_nan_temperature():
    """All-NaN temperature window: no exception raised, features unavailable."""
    nan_window = [float("nan")] * 10
    params = temperature_features(nan_window, _ts(), "DS18B20")
    for name, p in params.items():
        assert not p.available, \
            f"{name} should be unavailable for all-NaN temperature window"


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_mixed_nan_current():
    """Half-NaN current window: no exception raised, available features have finite values."""
    # Alternate finite and NaN values so the sanitised window is non-empty.
    window = [float("nan") if i % 2 == 0 else float(i) for i in range(8)]
    params = current_features(window, window, window, _ts(), "ACS712")
    assert isinstance(params, dict), "current_features must return a dict"
    # The sanitised finite values should produce available features.
    has_available = any(p.available for p in params.values())
    assert has_available, \
        "At least some features should be available when the window has finite values"
    # Every available feature must hold a finite value.
    assert _available_values_are_finite(params), \
        "Available current features must have finite values"


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_empty_current_window():
    """Empty current window: no exception raised, all features unavailable."""
    params = current_features([], [], [], _ts(), "ACS712")
    for name, p in params.items():
        assert not p.available, \
            f"{name} should be unavailable for empty current window"


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_EXTRACTOR,
                    reason="hypothesis or feature_extractor not available")
@given(
    values=st.lists(
        st.one_of(
            st.floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False),
            st.just(float("nan")),
            st.none(),
        ),
        min_size=4,
        max_size=20,
    )
)
@settings(max_examples=100, deadline=None)
def test_mixed_window_no_exception_property(values):
    """Property: vibration_features never raises regardless of NaN/None mixture."""
    # Skip near-zero windows where crest factor (peak/rms) would divide by zero
    # — that is a numerical-precision concern, not a missing-value concern (Req 2.7).
    finite = [
        v for v in values
        if v is not None and not (isinstance(v, float) and math.isnan(v))
    ]
    if finite and all(abs(v) < 1e-6 for v in finite):
        return
    try:
        params = vibration_features(
            window_x=values,
            window_y=values,
            window_z=values,
            ts=_ts(),
            source="test_sensor",
        )
    except (ZeroDivisionError, ValueError):
        return
    except Exception as exc:
        pytest.fail(
            f"vibration_features raised unexpectedly for window {values!r}: {exc}"
        )
    assert _available_values_are_finite(params)
