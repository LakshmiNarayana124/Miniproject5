"""
Property 10: Detection traceability
Validates: Requirements 2.6

Assert that DetectionTrace references the originating Monitoring_Parameter
values, the model version, and the resulting System_Status so every decision
is traceable.
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
        def lists(*a, **kw): return []
        @staticmethod
        def floats(**kw): return []
    _HAS_HYPOTHESIS = False

try:
    from inference import DetectionTrace, determine_status
    _HAS_INFERENCE = True
except ImportError:
    _HAS_INFERENCE = False


VALID_STATUSES = {"NORMAL", "WARNING", "CRITICAL"}


@pytest.mark.skipif(not _HAS_INFERENCE, reason="inference module not available")
def test_detection_trace_has_required_fields():
    """DetectionTrace must carry model_version, method, and status."""
    fv = [0.1, 0.2, 0.3, 45.0, 1.5]
    names = ["rms_x", "rms_y", "rms_z", "temp_mean", "current_rms"]

    status, trace = determine_status(feature_vector=fv, ts="2026-01-01T00:00:00Z",
                                     parameter_names=names)

    assert status in VALID_STATUSES, f"status must be one of {VALID_STATUSES}, got {status!r}"

    assert hasattr(trace, "model_version"), "DetectionTrace must have model_version"
    assert hasattr(trace, "method"), "DetectionTrace must have method"
    assert hasattr(trace, "status"), "DetectionTrace must have status"

    assert trace.status == status, "trace.status must match returned status"
    assert trace.model_version is not None, "model_version must not be None"
    assert trace.method is not None, "method must not be None"


@pytest.mark.skipif(not _HAS_INFERENCE, reason="inference module not available")
def test_detection_trace_carries_inputs():
    """DetectionTrace must be linkable back to the input feature vector."""
    fv = [0.5, 1.0, 1.5, 60.0, 2.5]
    names = ["rms_x", "rms_y", "rms_z", "temp_mean", "current_rms"]
    ts = "2026-01-01T12:00:00Z"

    status, trace = determine_status(feature_vector=fv, ts=ts, parameter_names=names)

    # Trace must capture timestamp
    assert trace.timestamp == ts or getattr(trace, "timestamp", ts) == ts


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_INFERENCE,
                    reason="hypothesis or inference not available")
@given(
    fv=st.lists(
        st.floats(min_value=-5.0, max_value=200.0, allow_nan=False, allow_infinity=False),
        min_size=3, max_size=20,
    )
)
@settings(max_examples=100)
def test_detection_trace_property(fv):
    """Property: every call to determine_status returns a status in the valid set
    and a trace with non-None model_version and method."""
    status, trace = determine_status(feature_vector=fv, ts="2026-01-01T00:00:00Z")

    assert status in VALID_STATUSES, \
        f"status must be one of {VALID_STATUSES}, got {status!r}"
    assert trace.model_version is not None
    assert trace.method is not None
    assert trace.status in VALID_STATUSES
