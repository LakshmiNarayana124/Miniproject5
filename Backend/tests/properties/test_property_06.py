"""
Property 6: FFT band-energy validity
Validates: Requirements 2.2

Assert at least four non-negative band-energy values for any vibration window.
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
    from feature_extractor import fft_band_energies
    _HAS_EXTRACTOR = True
except ImportError:
    _HAS_EXTRACTOR = False


def _ts():
    return datetime.now(timezone.utc).isoformat()


def _extract(window):
    """Call fft_band_energies with the same window on all three axes."""
    return fft_band_energies(
        window_x=window,
        window_y=window,
        window_z=window,
        ts=_ts(),
        source="test_sensor",
    )


def _band_params(result, axis):
    """Return all fft_band*_<axis> MonitoringParameters from result."""
    return [v for k, v in result.items() if k.endswith(f"_{axis}") and k.startswith("fft_band")]


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_at_least_four_bands():
    """fft_band_energies yields >= 4 band-energy values for a 32-sample window."""
    window = [math.sin(2 * math.pi * i / 32) for i in range(32)]
    result = _extract(window)

    for axis in ("x", "y", "z"):
        bands = _band_params(result, axis)
        assert len(bands) >= 4, \
            f"expected >= 4 bands for axis {axis}, got {len(bands)}"
        for param in bands:
            if param.available:
                assert param.value >= 0.0, \
                    f"{param.name} energy must be non-negative, got {param.value}"


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_band_energies_non_negative():
    """Band energies for a random sinusoid are all >= -1e-12 (floating-point tolerance)."""
    sample_rate = 10000.0
    n = 256
    # 200 Hz sinusoid
    window = [3.0 * math.sin(2 * math.pi * 200.0 * i / sample_rate) for i in range(n)]
    result = fft_band_energies(
        window_x=window,
        window_y=window,
        window_z=window,
        ts=_ts(),
        source="test_sinusoid",
        sample_rate=sample_rate,
    )
    for name, param in result.items():
        if param.available:
            assert param.value >= -1e-12, \
                f"Band energy {name} = {param.value} is below -1e-12"


@pytest.mark.skipif(not _HAS_EXTRACTOR, reason="feature_extractor not available")
def test_band_energies_all_axes_present():
    """Result contains entries for all three axes (x, y, z)."""
    window = [float(i % 5) for i in range(32)]
    result = _extract(window)
    for axis in ("x", "y", "z"):
        bands = _band_params(result, axis)
        assert len(bands) >= 4, \
            f"axis {axis} must have >= 4 band entries"


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_EXTRACTOR,
                    reason="hypothesis or feature_extractor not available")
@given(
    values=st.lists(
        st.floats(min_value=-5.0, max_value=5.0, allow_nan=False, allow_infinity=False),
        min_size=16,
        max_size=64,
    )
)
@settings(max_examples=100)
def test_band_energies_property(values):
    """Property: for any window, at least 4 non-negative band-energy params are produced."""
    result = _extract(values)

    for axis in ("x", "y", "z"):
        bands = _band_params(result, axis)
        assert len(bands) >= 4, \
            f"expected >= 4 band params for axis {axis}, got {len(bands)}"
        for param in bands:
            if param.available:
                assert param.value >= -1e-12, \
                    f"{param.name} energy {param.value} must be >= 0 (tolerance -1e-12)"
