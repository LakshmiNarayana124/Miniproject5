"""
Property 23: ISO vibration severity classification
Validates: Requirements 7.1

Assert that vibration values in each ISO 10816/20816 band are classified
into the correct severity zone (NORMAL / WARNING / CRITICAL).

ISO 10816-3 default thresholds (Group 2):
  normal_max  = 1.4 mm/s
  warning_max = 2.8 mm/s
  > 2.8 mm/s  = CRITICAL
"""
import os
import sys

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
        def floats(**kw): return []
    _HAS_HYPOTHESIS = False

try:
    from iso_standards import classify_vibration_severity
    _HAS_ISO = True
except ImportError:
    _HAS_ISO = False

# Actual ISO 10816-3 Group 2 default thresholds used by the implementation
NORMAL_MAX_MMS = 1.4
WARNING_MAX_MMS = 2.8


@pytest.mark.skipif(not _HAS_ISO, reason="iso_standards module not available")
def test_normal_zone_low_value():
    """A very low RMS value should be NORMAL (< 1.4 mm/s)."""
    result = classify_vibration_severity(rms_velocity_mm_s=0.5)
    assert result.upper() == "NORMAL", \
        f"RMS=0.5 mm/s (< {NORMAL_MAX_MMS}) must be NORMAL, got {result!r}"


@pytest.mark.skipif(not _HAS_ISO, reason="iso_standards module not available")
def test_warning_zone_mid_value():
    """A value between the normal and warning thresholds should be WARNING."""
    # 2.0 is between 1.4 (normal_max) and 2.8 (warning_max)
    result = classify_vibration_severity(rms_velocity_mm_s=2.0)
    assert result.upper() == "WARNING", \
        f"RMS=2.0 mm/s (between {NORMAL_MAX_MMS} and {WARNING_MAX_MMS}) must be WARNING, got {result!r}"


@pytest.mark.skipif(not _HAS_ISO, reason="iso_standards module not available")
def test_critical_zone_high_value():
    """A value above the warning threshold should be CRITICAL (> 2.8 mm/s)."""
    result = classify_vibration_severity(rms_velocity_mm_s=10.0)
    assert result.upper() == "CRITICAL", \
        f"RMS=10.0 mm/s (> {WARNING_MAX_MMS}) must be CRITICAL, got {result!r}"


@pytest.mark.skipif(not _HAS_ISO, reason="iso_standards module not available")
def test_boundaries_strictly_ordered():
    """Warning threshold < Critical threshold (zones strictly ordered)."""
    level_map = {
        0.5: classify_vibration_severity(rms_velocity_mm_s=0.5).upper(),
        2.0: classify_vibration_severity(rms_velocity_mm_s=2.0).upper(),
        5.0: classify_vibration_severity(rms_velocity_mm_s=5.0).upper(),
    }
    assert level_map[0.5] == "NORMAL"
    assert level_map[2.0] == "WARNING"
    assert level_map[5.0] == "CRITICAL"


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_ISO,
                    reason="hypothesis or iso_standards not available")
@given(rms=st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_severity_always_valid_status(rms):
    """Property: any non-negative RMS value yields a valid status string."""
    result = classify_vibration_severity(rms_velocity_mm_s=rms)
    assert result.upper() in ("NORMAL", "WARNING", "CRITICAL"), \
        f"classify_vibration_severity({rms}) returned unexpected value {result!r}"


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_ISO,
                    reason="hypothesis or iso_standards not available")
@given(
    rms_a=st.floats(min_value=0.0, max_value=49.9, allow_nan=False, allow_infinity=False),
    rms_b=st.floats(min_value=0.0, max_value=50.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100)
def test_severity_monotone(rms_a, rms_b):
    """Property: if rms_a < rms_b, severity(rms_a) is never more severe than severity(rms_b)."""
    assume(rms_a < rms_b)
    SEVERITY_RANK = {"NORMAL": 0, "WARNING": 1, "CRITICAL": 2}
    rank_a = SEVERITY_RANK[classify_vibration_severity(rms_velocity_mm_s=rms_a).upper()]
    rank_b = SEVERITY_RANK[classify_vibration_severity(rms_velocity_mm_s=rms_b).upper()]
    assert rank_a <= rank_b, \
        f"severity({rms_a}) = {rank_a} should be <= severity({rms_b}) = {rank_b}"
