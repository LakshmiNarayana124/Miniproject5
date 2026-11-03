"""
INTELLIWATCH - TRAINING PIPELINE TEST SUITE
Unit tests for the KAIST unified training-set loader (Requirement 1.1).

Covers filename parsing edge cases and a smoke load of the real KAIST
batch dataset. Property-based coverage is validated separately by the
Hypothesis suite (Property 1).
"""

import os
import unittest

# Allow importing the Backend module whether tests run from Backend/ or
# from the repository root.
import sys

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:  # pragma: no cover
    pd = None
    _HAS_PANDAS = False

from training_pipeline import (
    _parse_filename,
    _compute_dataset_hash,
    load_unified_training_set,
)

# Path to the real KAIST batch dataset, resolved relative to this file so the
# tests are independent of the current working directory.
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
_KAIST_BATCH = os.path.join(_REPO_ROOT, "KAIST", "features", "batch")


class TestParseFilename(unittest.TestCase):
    """Verify the KAIST filename grammar is parsed into label triples."""

    def test_bpfi_with_severity(self):
        self.assertEqual(
            _parse_filename("0Nm_BPFI_03_vibration_features.csv"),
            ("BPFI", "0Nm", "03"),
        )

    def test_bpfo_with_severity(self):
        self.assertEqual(
            _parse_filename("2Nm_BPFO_30_temperature_current_features.csv"),
            ("BPFO", "2Nm", "30"),
        )

    def test_misalign_normalised_to_misalignment(self):
        self.assertEqual(
            _parse_filename("4Nm_Misalign_05_vibration_features.csv"),
            ("Misalignment", "4Nm", "05"),
        )

    def test_misalignment_token_passes_through(self):
        self.assertEqual(
            _parse_filename("0Nm_Misalignment_01_vibration_features.csv"),
            ("Misalignment", "0Nm", "01"),
        )

    def test_unbalance_with_mass_severity(self):
        self.assertEqual(
            _parse_filename("2Nm_Unbalance_2239mg_temperature_current_features.csv"),
            ("Unbalance", "2Nm", "2239mg"),
        )

    def test_normal_has_no_severity(self):
        self.assertEqual(
            _parse_filename("4Nm_Normal_vibration_features.csv"),
            ("Normal", "4Nm", None),
        )

    def test_accepts_full_path(self):
        self.assertEqual(
            _parse_filename("/some/dir/0Nm_BPFI_10_vibration_features.csv"),
            ("BPFI", "0Nm", "10"),
        )

    def test_unparseable_returns_none_triple(self):
        self.assertEqual(_parse_filename("garbage.csv"), (None, None, None))


class TestLoadUnifiedTrainingSet(unittest.TestCase):
    """Smoke-load the real KAIST dataset and validate the contract."""

    def setUp(self):
        if not os.path.isdir(_KAIST_BATCH):
            self.skipTest(f"KAIST batch dataset not found at {_KAIST_BATCH}")

    def test_returns_expected_structure(self):
        result = load_unified_training_set(_KAIST_BATCH)
        self.assertIn("X", result)
        self.assertIn("y", result)
        self.assertIn("meta", result)
        meta = result["meta"]
        for key in ("hash", "files", "faults", "loads", "severities"):
            self.assertIn(key, meta)

    def test_covers_all_fault_types(self):
        meta = load_unified_training_set(_KAIST_BATCH)["meta"]
        # Requirement 1.1: Normal, BPFI, BPFO, Misalignment, Unbalance.
        self.assertEqual(
            meta["faults"],
            {"Normal", "BPFI", "BPFO", "Misalignment", "Unbalance"},
        )

    def test_covers_all_load_levels(self):
        meta = load_unified_training_set(_KAIST_BATCH)["meta"]
        self.assertEqual(meta["loads"], {"0Nm", "2Nm", "4Nm"})

    def test_covers_both_modalities(self):
        meta = load_unified_training_set(_KAIST_BATCH)["meta"]
        self.assertEqual(meta["modalities"], {"vibration", "temperature_current"})

    def test_labels_align_with_features(self):
        result = load_unified_training_set(_KAIST_BATCH)
        X, y = result["X"], result["y"]
        if _HAS_PANDAS:
            self.assertEqual(len(y), len(X))
        else:
            self.assertEqual(len(y), len(X))

    def test_every_fault_load_on_disk_is_loaded(self):
        """Property 1 (example form): every (fault, load) on disk is present."""
        import glob
        result = load_unified_training_set(_KAIST_BATCH)
        y = result["y"]

        # Collect (fault, load) tuples directly from filenames on disk.
        on_disk = set()
        for modality in ("vibration", "temperature_current"):
            pattern = os.path.join(_KAIST_BATCH, modality, "*_features.csv")
            for path in glob.glob(pattern):
                fault, load, _sev = _parse_filename(path)
                if fault is not None:
                    on_disk.add((fault, load))

        loaded = {(ft, ll) for ft, ll, _ in y}
        self.assertTrue(
            on_disk.issubset(loaded),
            f"Missing (fault, load) tuples in loaded set: "
            f"{on_disk - loaded}",
        )

    def test_dataset_hash_is_sha256_hex(self):
        meta = load_unified_training_set(_KAIST_BATCH)["meta"]
        self.assertEqual(len(meta["hash"]), 64)
        int(meta["hash"], 16)  # must be valid hex.

    def test_non_zero_windows_per_fault_load(self):
        """Every loaded (fault, load) tuple has a non-zero window count."""
        from collections import Counter
        y = load_unified_training_set(_KAIST_BATCH)["y"]
        counts = Counter((ft, ll) for ft, ll, _ in y)
        self.assertTrue(counts, "expected at least one window")
        for key, count in counts.items():
            self.assertGreater(count, 0, f"zero windows for {key}")


class TestDatasetHash(unittest.TestCase):

    def test_hash_is_deterministic(self):
        entries = [("vibration/a.csv", 100), ("temperature_current/b.csv", 50)]
        self.assertEqual(_compute_dataset_hash(entries), _compute_dataset_hash(entries))

    def test_hash_changes_with_row_count(self):
        a = _compute_dataset_hash([("vibration/a.csv", 100)])
        b = _compute_dataset_hash([("vibration/a.csv", 101)])
        self.assertNotEqual(a, b)

    def test_hash_changes_with_file_list(self):
        a = _compute_dataset_hash([("vibration/a.csv", 100)])
        b = _compute_dataset_hash([("vibration/a.csv", 100), ("vibration/b.csv", 1)])
        self.assertNotEqual(a, b)

    def test_empty_entries_hash_is_valid_hex(self):
        h = _compute_dataset_hash([])
        self.assertEqual(len(h), 64)


class TestMissingDirectories(unittest.TestCase):
    """The loader degrades gracefully when directories are missing."""

    def test_nonexistent_root_returns_empty_set(self):
        result = load_unified_training_set("/no/such/KAIST/path/here")
        meta = result["meta"]
        self.assertEqual(meta["files"], [])
        self.assertEqual(meta["row_count"], 0)
        self.assertEqual(set(), meta["faults"])
        self.assertEqual(len(meta["hash"]), 64)


if __name__ == "__main__":
    unittest.main()
