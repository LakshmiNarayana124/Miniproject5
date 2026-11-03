"""
Property 24: Threshold source documentation
Validates: Requirements 7.3

Assert that every threshold definition in sensor_config.py carries a
non-empty documented source standard OR is flagged equipment_specific=True
(inactive until operator confirms), as required by Req 7.3 and 7.4.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from sensor_config import get_all_sensor_configs
    _HAS_CONFIG = True
except ImportError:
    _HAS_CONFIG = False


@pytest.mark.skipif(not _HAS_CONFIG, reason="sensor_config module not available")
def test_all_thresholds_have_source_or_equipment_specific():
    """Every operating_limits dict must have a non-empty source OR equipment_specific=True."""
    configs = get_all_sensor_configs()
    for sensor_type, config in configs.items():
        limits = config.get("operating_limits", {})
        source = limits.get("source")
        equipment_specific = limits.get("equipment_specific", False)

        # Must satisfy: non-empty source string OR equipment_specific flag
        has_source = isinstance(source, str) and len(source.strip()) > 0
        assert has_source or equipment_specific, (
            f"Sensor '{sensor_type}': operating_limits must have a non-empty source "
            f"OR equipment_specific=True (Req 7.3). Got source={source!r}, "
            f"equipment_specific={equipment_specific}"
        )


@pytest.mark.skipif(not _HAS_CONFIG, reason="sensor_config module not available")
def test_vibration_has_iso_source():
    """Vibration sensor threshold must reference an ISO standard."""
    configs = get_all_sensor_configs()
    vib = configs.get("vibration", {})
    source = vib.get("operating_limits", {}).get("source", "")
    assert source, "Vibration operating_limits must have a non-empty source"
    assert "ISO" in source.upper() or vib["operating_limits"].get("equipment_specific"), \
        f"Vibration source should reference ISO standard, got: {source!r}"


@pytest.mark.skipif(not _HAS_CONFIG, reason="sensor_config module not available")
def test_temperature_has_source():
    """Temperature sensor threshold must have a source or equipment_specific flag."""
    configs = get_all_sensor_configs()
    temp = configs.get("temperature", {})
    limits = temp.get("operating_limits", {})
    source = limits.get("source", "")
    eq_specific = limits.get("equipment_specific", False)
    assert source or eq_specific, \
        "Temperature operating_limits must have source or equipment_specific=True"


@pytest.mark.skipif(not _HAS_CONFIG, reason="sensor_config module not available")
def test_current_has_source():
    """Current sensor threshold must have a source or equipment_specific flag."""
    configs = get_all_sensor_configs()
    curr = configs.get("current", {})
    limits = curr.get("operating_limits", {})
    source = limits.get("source", "")
    eq_specific = limits.get("equipment_specific", False)
    assert source or eq_specific, \
        "Current operating_limits must have source or equipment_specific=True"


@pytest.mark.skipif(not _HAS_CONFIG, reason="sensor_config module not available")
def test_equipment_specific_sensors_have_informational_defaults():
    """Sensors marked equipment_specific=True must have numeric defaults
    (informational reference values) rather than None, so the UI can show
    a reference value even before operator confirmation."""
    configs = get_all_sensor_configs()
    for sensor_type, config in configs.items():
        limits = config.get("operating_limits", {})
        if limits.get("equipment_specific"):
            # Should have at least one numeric limit as an informational reference
            numeric_values = [
                v for k, v in limits.items()
                if k not in ("source", "equipment_specific") and isinstance(v, (int, float))
            ]
            assert len(numeric_values) >= 1, (
                f"Sensor '{sensor_type}' is equipment_specific but has no numeric "
                f"reference values in operating_limits — at least one informational "
                f"default should be present"
            )
