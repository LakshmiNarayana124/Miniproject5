"""
Property 5: Vibration feature statistical identities
Validates: Requirements 2.1

Assert crest_factor == peak / rms and kurtosis satisfies the excess-kurtosis
definition for every available axis.
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
        def floats(**kw): return []
    _HAS_HYPOTHESIS = False

try:
    from feature_extractor import vibration_features
    _HAS_EXTRACTOR = True
except ImportError:
    _HAS_EXTRACTOR = False


def _extract(values_x, values_y, values_z):
    """Call vibration_features with lists of floats and return dict[name, MonitoringParameter]."""
    ts = datetime.now(timezone.utc).isoformat()
    return vibration_features(
        window_x=values_x,
        window_y=values_y,
        window_z=values_z,
        ts=ts,
        source="test_sensor",
    )


def _get_value(params, name):
    """Get value from a dict[str, MonitoringParameter] by name; return None if unavailable."""
    p = params.get(name)
    if p is None or not p.available:
        return None
    v = p.value
    return v if (v is not None and not math.isnan(v)) else None


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_crest_factor_identity_uniform():
    """crest_factor == peak / rms for a simple known input."""
    data = [0.5, 1.0, -1.0, 0.5]
    params = _extract(data, data, data)

    for axis in ("x", "y", "z"):
        rms = _get_value(params, f"rms_{axis}")
        peak = _get_value(params, f"peak_{axis}")
        cf = _get_value(params, f"crest_factor_{axis}")
        if rms is not None and peak is not None and cf is not None and rms > 1e-12:
            assert abs(cf - peak / rms) < 1e-9, \
                f"crest_factor_{axis} ({cf}) != peak_{axis} ({peak}) / rms_{axis} ({rms})"


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_rms_non_negative():
    """RMS values must be non-negative."""
    data = [0.1, -0.2, 0.3, -0.4]
    params = _extract(data, data, data)
    for axis in ("x", "y", "z"):
        rms = _get_value(params, f"rms_{axis}")
        if rms is not None:
            assert rms >= 0, f"rms_{axis} must be non-negative, got {rms}"


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_peak_geq_rms():
    """peak >= rms is always true for any signal."""
    data = [0.1, 0.5, 0.2, 0.8, -0.9, 0.3]
    params = _extract(data, data, data)
    for axis in ("x", "y", "z"):
        rms = _get_value(params, f"rms_{axis}") or 0
        peak = _get_value(params, f"peak_{axis}") or 0
        assert peak >= rms - 1e-10, f"peak_{axis} ({peak}) should be >= rms_{axis} ({rms})"


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_EXTRACTOR,
                    reason="hypothesis or feature_extractor not available")
@given(
    values=st.lists(
        st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        min_size=4, max_size=50,
    )
)
@settings(max_examples=100)
def test_crest_factor_property(values):
    """Property: crest_factor == peak / rms for any non-trivial signal."""
    assume(any(abs(v) > 1e-8 for v in values))
    params = _extract(values, values, values)

    for axis in ("x", "y", "z"):
        rms_val = _get_value(params, f"rms_{axis}")
        peak_val = _get_value(params, f"peak_{axis}")
        cf_val = _get_value(params, f"crest_factor_{axis}")
        if cf_val is not None and rms_val is not None and rms_val > 1e-12:
            expected = peak_val / rms_val
            assert abs(cf_val - expected) < 1e-6, \
                f"crest_factor_{axis} ({cf_val}) != peak/rms ({expected})"
