"""
Property 39: Model-degradation alerting
Validates: Requirements 14.4

Alert raised when a deployed metric falls >0.05 below its promotion threshold.
"""
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    from obs_service import (
        check_model_degradation,
        get_degradation_alerts,
        DEGRADATION_MARGIN,
        TABULAR_ACCURACY_TARGET,
        UNSUPERVISED_F1_TARGET,
        set_current_status,
    )
    import database
    _HAS_OBS = True
except ImportError:
    _HAS_OBS = False
    DEGRADATION_MARGIN = 0.05
    TABULAR_ACCURACY_TARGET = 0.92
    UNSUPERVISED_F1_TARGET = 0.90


def _setup(tmp_dir):
    database._DB_PATH = os.path.join(tmp_dir, "test_deg.db")
    database.initialize_database()


@pytest.mark.skipif(not _HAS_OBS, reason="obs_service not available")
def test_degradation_margin_is_0_05():
    """DEGRADATION_MARGIN constant is 0.05."""
    assert DEGRADATION_MARGIN == pytest.approx(0.05), \
        f"DEGRADATION_MARGIN should be 0.05, got {DEGRADATION_MARGIN}"


@pytest.mark.skipif(not _HAS_OBS, reason="obs_service not available")
def test_check_degradation_does_not_raise():
    """check_model_degradation() runs without raising."""
    with tempfile.TemporaryDirectory() as tmp:
        _setup(tmp)
        try:
            check_model_degradation()
        except Exception as exc:
            pytest.fail(f"check_model_degradation raised: {exc}")


@pytest.mark.skipif(not _HAS_OBS, reason="obs_service not available")
def test_get_degradation_alerts_returns_list():
    """get_degradation_alerts() returns a list."""
    with tempfile.TemporaryDirectory() as tmp:
        _setup(tmp)
        result = get_degradation_alerts()
        assert isinstance(result, list)


@pytest.mark.skipif(not _HAS_OBS, reason="obs_service not available")
def test_no_alert_when_no_models():
    """With no deployed models, no degradation alerts are raised."""
    with tempfile.TemporaryDirectory() as tmp:
        _setup(tmp)
        check_model_degradation()
        alerts = get_degradation_alerts()
        assert alerts == [], f"Expected empty alerts with no models, got {alerts}"


@pytest.mark.skipif(not _HAS_OBS, reason="obs_service not available")
def test_tabular_target_in_range():
    """TABULAR_ACCURACY_TARGET is in (0, 1]."""
    assert 0 < TABULAR_ACCURACY_TARGET <= 1.0
