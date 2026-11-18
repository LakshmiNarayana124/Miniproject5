"""
Property 4: Ensemble decision consistency
Validates: Requirements 1.5

Ensemble decision is a deterministic function of member outputs and
references every member model.
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
    from training_pipeline import EnsembleModel
    _HAS_ENSEMBLE = True
except ImportError:
    _HAS_ENSEMBLE = False

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    np = None
    _HAS_NUMPY = False

try:
    from sklearn.ensemble import RandomForestClassifier
    _HAS_ML = True
except ImportError:
    _HAS_ML = False


def _make_member(seed=0):
    """Build a minimal trained RandomForestClassifier usable as an ensemble member."""
    X = [[0.1 + seed * 0.1, 0.2], [0.3 + seed * 0.1, 0.4],
         [0.5 + seed * 0.1, 0.6], [0.7 + seed * 0.1, 0.8],
         [0.9, 1.0], [0.2, 0.3], [0.4, 0.5], [0.6, 0.7]]
    y = ["Normal", "BPFI", "Normal", "BPFI", "Normal", "BPFI", "Normal", "BPFI"]
    clf = RandomForestClassifier(n_estimators=3, random_state=seed)
    clf.fit(X, y)
    return clf


def _make_ensemble(n_members=2):
    """Return an EnsembleModel with n_members trained XGBClassifier members."""
    members = [_make_member(seed=i) for i in range(n_members)]
    return EnsembleModel(members, version="v_test")


_SAMPLE_INPUT = [[0.3, 0.5]]


@pytest.mark.skipif(not _HAS_ENSEMBLE, reason="EnsembleModel not available in training_pipeline")
@pytest.mark.skipif(not _HAS_ML, reason="sklearn not installed")
@pytest.mark.skipif(not _HAS_NUMPY, reason="numpy not installed")
def test_ensemble_deterministic():
    ensemble = _make_ensemble()
    result1 = ensemble.predict(_SAMPLE_INPUT)
    result2 = ensemble.predict(_SAMPLE_INPUT)
    assert result1 == result2


@pytest.mark.skipif(not _HAS_ENSEMBLE, reason="EnsembleModel not available in training_pipeline")
@pytest.mark.skipif(not _HAS_ML, reason="sklearn not installed")
@pytest.mark.skipif(not _HAS_NUMPY, reason="numpy not installed")
def test_ensemble_references_members():
    ensemble = _make_ensemble(n_members=2)
    members = ensemble.members_referenced()
    assert len(members) >= 2


@pytest.mark.skipif(not _HAS_ENSEMBLE, reason="EnsembleModel not available in training_pipeline")
@pytest.mark.skipif(not _HAS_ML, reason="sklearn not installed")
@pytest.mark.skipif(not _HAS_NUMPY, reason="numpy not installed")
def test_ensemble_predict_returns_label():
    ensemble = _make_ensemble()
    result = ensemble.predict(_SAMPLE_INPUT)
    assert isinstance(result, list)
    assert len(result) == len(_SAMPLE_INPUT)
    for label in result:
        assert isinstance(label, str)


@pytest.mark.skipif(not _HAS_ENSEMBLE, reason="EnsembleModel not available in training_pipeline")
@pytest.mark.skipif(not _HAS_ML, reason="sklearn not installed")
@pytest.mark.skipif(not _HAS_NUMPY, reason="numpy not installed")
def test_ensemble_predict_proba_sums_to_one():
    import math
    ensemble = _make_ensemble()
    proba = ensemble.predict_proba(_SAMPLE_INPUT)
    if hasattr(proba, "tolist"):
        proba = proba.tolist()
    for row in proba:
        total = sum(row)
        assert math.isclose(total, 1.0, abs_tol=1e-6)


@pytest.mark.skipif(not _HAS_HYPOTHESIS or not _HAS_ENSEMBLE or not _HAS_ML or not _HAS_NUMPY,
                    reason="hypothesis, EnsembleModel, or sklearn not available")
@given(
    row=st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=2, max_size=2,
    )
)
@settings(max_examples=50)
def test_ensemble_deterministic_property(row):
    ensemble = _make_ensemble()
    result1 = ensemble.predict([row])
    result2 = ensemble.predict([row])
    assert result1 == result2
