"""
Property 9: Monitoring-parameter serialization round-trip
Validates: Requirements 2.5

Assert that MonitoringParameter serializes to a dict and deserializes back
to an equal object.
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
        def text(**kw): return []
        @staticmethod
        def sampled_from(seq): return []
        @staticmethod
        def one_of(*a): return []
        @staticmethod
        def floats(**kw): return []
        @staticmethod
        def none(): return []
        @staticmethod
        def booleans(): return []
    _HAS_HYPOTHESIS = False

try:
    from feature_extractor import MonitoringParameter
    _HAS_MP = True
except ImportError:
    _HAS_MP = False


@pytest.mark.skipif(not _HAS_MP, reason="MonitoringParameter not available")
def test_round_trip_basic():
    """to_dict / from_dict preserves all fields."""
    ts = datetime.now(timezone.utc).isoformat()
    mp = MonitoringParameter(
        name="test_param",
        unit="g",
        sensor_source="vibration",
        timestamp=ts,
        value=1.23,
        schema_version="1",
        available=True,
    )
    d = mp.to_dict()
    mp2 = MonitoringParameter.from_dict(d)

    assert mp2.name == mp.name
    assert mp2.unit == mp.unit
    assert mp2.sensor_source == mp.sensor_source
    assert mp2.timestamp == mp.timestamp
    assert mp2.value == mp.value
    assert mp2.schema_version == mp.schema_version
    assert mp2.available == mp.available


@pytest.mark.skipif(not _HAS_MP, reason="MonitoringParameter not available")
def test_round_trip_none_value():
    """None value is normalized to NaN and available=False through round-trip."""
    ts = datetime.now(timezone.utc).isoformat()
    mp = MonitoringParameter(
        name="missing",
        unit="°C",
        sensor_source="temperature",
        timestamp=ts,
        value=None,
        schema_version="1",
        available=False,
    )
    # __post_init__ converts None to NaN
    assert math.isnan(mp.value), "None value should be normalized to NaN by __post_init__"
    assert mp.available is False

    d = mp.to_dict()
    mp2 = MonitoringParameter.from_dict(d)
    assert math.isnan(mp2.value), "Deserialized NaN value must remain NaN"
    assert mp2.available is False


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_MP,
                    reason="hypothesis or MonitoringParameter not available")
@given(
    name=st.text(min_size=1, max_size=50),
    unit=st.sampled_from(["g", "°C", "A", "mm/s"]),
    value=st.one_of(
        st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
        st.none(),
    ),
    available=st.booleans(),
)
@settings(max_examples=100)
def test_round_trip_property(name, unit, value, available):
    """Property: round-trip preserves name, unit, value, and available for any input."""
    ts = datetime.now(timezone.utc).isoformat()
    mp = MonitoringParameter(
        name=name,
        unit=unit,
        sensor_source="vibration",
        timestamp=ts,
        value=value,
        schema_version="1",
        available=available,
    )
    d = mp.to_dict()
    mp2 = MonitoringParameter.from_dict(d)

    assert mp2.name == mp.name
    assert mp2.unit == mp.unit
    assert mp2.available == mp.available
    # Float NaN identity special case
    if mp.value is None:
        assert mp2.value is None
    elif isinstance(mp.value, float) and not math.isnan(mp.value):
        assert mp2.value == mp.value
