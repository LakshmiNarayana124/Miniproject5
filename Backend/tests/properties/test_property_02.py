
"""
Property 2: Model persistence round-trip
Validates: Requirements 1.6

Assert that a model artifact persisted to disk and reloaded preserves its
version identifier, training timestamp, and dataset hash.
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
)

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    _HAS_HYPOTHESIS = True

except ImportError:

    def given(*a, **kw):
        return lambda f: f

    def settings(*a, **kw):
        return lambda f: f

    class st:  # noqa: N801
        @staticmethod
        def from_regex(*a, **kw):
            return []

    _HAS_HYPOTHESIS = False


try:
    from training_pipeline import (
        persist_model,
        load_model_artifact,
        TabularModel
    )

    import xgboost as xgb
    from sklearn.preprocessing import LabelEncoder
    import numpy as np

    _HAS_DEPS = True

except ImportError:
    _HAS_DEPS = False


def _make_tiny_tabular_model(version="v_test"):
    """Build a minimal TabularModel for round-trip tests."""

    X = np.array([
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
        [0.7, 0.8, 0.9]
    ])

    y_raw = ["Normal", "BPFI", "Normal"]

    le = LabelEncoder()
    y = le.fit_transform(y_raw)

    est = xgb.XGBClassifier(
        n_estimators=3,
        max_depth=2,
        eval_metric="mlogloss",
        random_state=42
    )

    est.fit(X, y)

    return TabularModel(
        est,
        le,
        ["f0", "f1", "f2"],
        version
    )


@pytest.mark.skipif(
    not _HAS_DEPS,
    reason="xgboost/numpy not installed"
)
def test_model_persistence_round_trip_basic():
    """Persist a model and reload it; check version, timestamp, and dataset hash."""

    with tempfile.TemporaryDirectory() as tmp:

        version = "v20260101_120000"
        dataset_hash = "abc123deadbeef"

        metrics = {
            "accuracy": 0.95,
            "f1": 0.94
        }

        model = _make_tiny_tabular_model(version)

        manifest = persist_model(
            model,
            "tabular",
            tmp,
            dataset_hash,
            metrics=metrics,
            version=version
        )

        assert manifest["version"] == version, (
            "version must be preserved"
        )

        assert manifest["dataset_hash"] == dataset_hash, (
            "dataset_hash must be preserved"
        )

        assert "training_timestamp" in manifest, (
            "training_timestamp must be present"
        )

        assert manifest["training_timestamp"] is not None

        # Reload and verify manifest file on disk matches.
        manifest_path = os.path.join(
            tmp,
            "tabular",
            version,
            "manifest.json"
        )

        assert os.path.isfile(manifest_path), (
            "manifest.json must exist on disk"
        )

        with open(manifest_path, encoding="utf-8") as f:
            on_disk = json.load(f)

        assert on_disk["version"] == version
        assert on_disk["dataset_hash"] == dataset_hash
        assert "training_timestamp" in on_disk


@pytest.mark.skipif(
    not _HAS_DEPS,
    reason="xgboost/numpy not installed"
)
def test_model_persistence_multiple_versions():
    """Each version stores an independent artifact directory."""

    with tempfile.TemporaryDirectory() as tmp:

        for version in [
            "v20260101_000000",
            "v20260102_000000"
        ]:

            model = _make_tiny_tabular_model(version)

            persist_model(
                model,
                "tabular",
                tmp,
                f"hash_{version}",
                version=version
            )

        dirs = os.listdir(
            os.path.join(tmp, "tabular")
        )

        assert set(dirs) == {
            "v20260101_000000",
            "v20260102_000000"
        }, "each version gets its own directory"


@pytest.mark.skipif(
    not _HAS_HYPOTHESIS or not _HAS_DEPS,
    reason="hypothesis or deps not installed"
)
@given(
    version=st.from_regex(
        r"v\d{8}_\d{6}",
        fullmatch=True
    ),
    dataset_hash=st.from_regex(
        r"[0-9a-f]{8,16}",
        fullmatch=True
    )
)
@settings(
    max_examples=10,
    deadline=None
)
def test_model_persistence_property(version, dataset_hash):
    """
    Property: round-tripped version and hash match inputs
    for any valid inputs.
    """

    with tempfile.TemporaryDirectory() as tmp:

        model = _make_tiny_tabular_model(version)

        manifest = persist_model(
            model,
            "tabular",
            tmp,
            dataset_hash,
            metrics={},
            version=version
        )

        assert manifest["version"] == version
        assert manifest["dataset_hash"] == dataset_hash
