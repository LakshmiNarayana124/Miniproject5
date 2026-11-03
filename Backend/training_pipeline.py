"""
INTELLIWATCH - TRAINING PIPELINE
Version: 1.0

Purpose:
- Load the KAIST bearing-fault feature dataset into a single unified
  training set covering every Fault_Type, Load_Level, and Severity
  combination present on disk (Requirement 1.1).
- Parse the KAIST feature-CSV filename grammar
  ``{Load}_{Condition}_{Severity}_{modality}_features.csv`` into a label
  triple ``(fault_type, load_level, severity)``.
- Concatenate all vibration and temperature/current feature windows into
  one frame and compute a SHA-256 ``dataset_hash`` over the sorted file
  list + per-file row counts so that a training run is reproducibly tied
  to a precise dataset snapshot.

Dependencies:
- Python standard library (``os``, ``csv``, ``hashlib``, ``logging``).
- ``pandas`` is used for CSV loading and concatenation when available; if it
  is not installed the loader falls back to the ``csv`` module and returns
  ``X`` as a list of row dictionaries instead of a DataFrame.

NOTE:
This is the first layer of the offline Training_Pipeline (design §4.1). Later
tasks extend this module with tabular / unsupervised / sequence / ensemble
training, validation reports, and model persistence. For now only the
unified data loader and its filename parser are defined.
"""

import os
import csv
import json
import math
import hashlib
import logging
import pickle
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple, Any

try:
    import numpy as np

    _HAS_NUMPY = True
except ImportError:
    np = None
    _HAS_NUMPY = False

try:
    import pandas as pd  # type: ignore

    _HAS_PANDAS = True
except ImportError:  # pragma: no cover
    pd = None  # type: ignore
    _HAS_PANDAS = False

# Optional ML backends (graceful degradation when absent)
try:
    import xgboost as xgb  # type: ignore

    _HAS_XGBOOST = True
except ImportError:
    xgb = None
    _HAS_XGBOOST = False

try:
    from sklearn.ensemble import IsolationForest  # type: ignore
    from sklearn.preprocessing import LabelEncoder  # type: ignore
    from sklearn.model_selection import train_test_split  # type: ignore
    from sklearn.metrics import (  # type: ignore
        accuracy_score,
        precision_score,
        recall_score,
        f1_score,
        confusion_matrix,
    )

    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False

try:
    import torch
    import torch.nn as nn

    _HAS_TORCH = True
except ImportError:
    torch = None
    nn = None
    _HAS_TORCH = False


logger = logging.getLogger(__name__)


# ============================================================
# 1. CONSTANTS
# ============================================================

BATCH_SIZE = 10000  # Mini-batch size for large datasets (Req 9.2)

# Accuracy promotion thresholds (Req 10.1-10.4)
TABULAR_ACCURACY_TARGET = 0.92
UNSUPERVISED_F1_TARGET = 0.90
FALSE_ALARM_RATE_MAX = 0.05

# Priority map for control-signal intents
PRIORITY_SHUTDOWN = 3
PRIORITY_DE_RATE = 2
PRIORITY_RUN = 1

STATUS_TO_INTENT = {
    "CRITICAL": "SHUTDOWN",
    "WARNING": "DE_RATE",
    "NORMAL": "RUN",
}

# Sub-directories under ``dataset_root`` that hold feature CSVs. Each
# directory name is also the modality label recorded per window.
_MODALITIES: Tuple[str, ...] = ("vibration", "temperature_current")

# Canonical Fault_Type values (see requirements glossary) mapped from the
# raw token used in KAIST filenames. ``Misalign`` is normalised to the
# canonical ``Misalignment``; ``Normal`` / ``BPFI`` / ``BPFO`` / ``Unbalance``
# are passed through unchanged.
_FAULT_ALIASES: Dict[str, str] = {
    "Normal": "Normal",
    "BPFI": "BPFI",
    "BPFO": "BPFO",
    "Misalign": "Misalignment",
    "Misalignment": "Misalignment",
    "Unbalance": "Unbalance",
}

# Feature CSV filename suffix and extension.
_FEATURES_SUFFIX = "_features.csv"


# ============================================================
# 2. FILENAME PARSING
# ============================================================


def _parse_filename(
    filename: str,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Parse a KAIST feature-CSV filename into ``(fault_type, load_level, severity)``.

    The filename grammar is
    ``{Load}_{Condition}_{Severity}_{modality}_features.csv`` where the
    ``{Severity}`` segment is omitted for the ``Normal`` condition, e.g.
    ``4Nm_Normal_vibration_features.csv``.

    Examples
    --------
    >>> _parse_filename("0Nm_BPFI_03_vibration_features.csv")
    ('BPFI', '0Nm', '03')
    >>> _parse_filename("4Nm_Normal_vibration_features.csv")
    ('Normal', '4Nm', None)
    >>> _parse_filename("2Nm_Unbalance_2239mg_temperature_current_features.csv")
    ('Unbalance', '2Nm', '2239mg')
    >>> _parse_filename("0Nm_Misalign_01_vibration_features.csv")
    ('Misalignment', '0Nm', '01')

    Parameters
    ----------
    filename : str
        Bare file name or full path of a KAIST feature CSV.

    Returns
    -------
    tuple of (fault_type, load_level, severity) or (None, None, None)
        ``severity`` is ``None`` for the Normal condition. The whole triple
        is ``(None, None, None)`` when the filename cannot be parsed.
    """
    name = os.path.basename(filename)

    # Strip extension and ``_features`` suffix to obtain the label stem.
    if name.lower().endswith(".csv"):
        name = name[:-4]
    if name.endswith("_features"):
        name = name[: -len("_features")]

    # Strip the trailing modality token so only the label part remains.
    # Modalities are matched longest-first so ``temperature_current``
    # (which contains an underscore) is removed as a whole.
    label_stem = name
    for modality in _MODALITIES:
        suffix = "_" + modality
        if label_stem.endswith(suffix):
            label_stem = label_stem[: -len(suffix)]
            break

    tokens = label_stem.split("_")
    if len(tokens) < 2:
        logger.warning("Unparseable KAIST filename (too few tokens): %s", filename)
        return None, None, None

    load_level = tokens[0]
    condition_tokens = tokens[1:]

    # Normal carries no severity segment.
    if len(condition_tokens) == 1 and condition_tokens[0].lower() == "normal":
        return "Normal", load_level, None

    fault_raw = condition_tokens[0]
    fault_type = _FAULT_ALIASES.get(fault_raw, fault_raw)
    severity = "_".join(condition_tokens[1:]) if len(condition_tokens) > 1 else None
    return fault_type, load_level, severity


# ============================================================
# 3. UNIFIED TRAINING-SET LOADER
# ============================================================


def _iter_feature_files(root: str) -> List[Tuple[str, str, str]]:
    """Collect every feature CSV under ``root``.

    Walks each known modality sub-directory and returns a sorted list of
    ``(relative_path, abs_path, modality)`` tuples. Missing modality
    directories are logged and skipped so the loader degrades gracefully
    when only part of the dataset is present.
    """
    found: List[Tuple[str, str, str]] = []
    for modality in _MODALITIES:
        mod_dir = os.path.join(root, modality)
        if not os.path.isdir(mod_dir):
            logger.warning("KAIST modality directory missing: %s", mod_dir)
            continue
        for fname in sorted(os.listdir(mod_dir)):
            if not fname.endswith(_FEATURES_SUFFIX):
                continue
            rel_path = f"{modality}/{fname}"
            abs_path = os.path.join(mod_dir, fname)
            found.append((rel_path, abs_path, modality))
    # Sort by relative path for deterministic ordering.
    found.sort(key=lambda item: item[0])
    return found


def _compute_dataset_hash(
    entries: List[Tuple[str, int]],
) -> str:
    """Compute a SHA-256 hash over a sorted ``[(relative_path, row_count)]`` list.

    The hash pins the training run to a precise dataset snapshot: adding,
    removing, or resizing any feature file changes it.
    """
    hasher = hashlib.sha256()
    for rel_path, row_count in entries:
        hasher.update(f"{rel_path}|{row_count}\n".encode("utf-8"))
    return hasher.hexdigest()


def load_unified_training_set(
    dataset_root: str = "KAIST/features/batch",
) -> Dict:
    """Load every KAIST feature file into a single unified training set.

    Walks ``dataset_root/vibration/`` and ``dataset_root/temperature_current/``,
    parses each CSV filename into ``(fault_type, load_level, severity)``
    labels (Requirement 1.1), and concatenates all windows into one frame.
    A SHA-256 ``dataset_hash`` is computed over the sorted file list + per-file
    row counts so the snapshot is reproducible.

    Parameters
    ----------
    dataset_root : str
        Path to the directory containing the ``vibration`` and
        ``temperature_current`` modality folders.

    Returns
    -------
    dict
        ``{"X": features, "y": labels, "meta": {...}}`` where:

        - ``X`` is a ``pandas.DataFrame`` of every window with its original
          CSV columns plus ``modality``, ``fault_type``, ``load_level``, and
          ``severity`` columns (or a list of row dicts when pandas is absent).
        - ``y`` is a list of ``(fault_type, load_level, severity)`` tuples
          aligned 1:1 with the rows of ``X``.
        - ``meta`` carries ``hash``, ``files``, ``faults``, ``loads``,
          ``severities``, ``modalities``, ``row_count``, and
          ``availability_columns``.

    Missing modality directories are logged and skipped; the loader returns
    whatever data is available.
    """
    root = os.path.abspath(dataset_root)
    files = _iter_feature_files(root)

    if not files:
        logger.warning(
            "No KAIST feature files found under %s; returning an empty "
            "training set.",
            root,
        )

    # Accumulators.
    faults: Set[str] = set()
    loads: Set[str] = set()
    severities: Set[Optional[str]] = set()
    modalities: Set[str] = set()
    availability_columns: Set[str] = set()

    hash_entries: List[Tuple[str, int]] = []
    labels: List[Tuple[Optional[str], Optional[str], Optional[str]]] = []

    if _HAS_PANDAS:
        frames: List["pd.DataFrame"] = []
        for rel_path, abs_path, modality in files:
            frame = pd.read_csv(abs_path)
            row_count = len(frame)
            fault_type, load_level, severity = _parse_filename(rel_path)

            frame["modality"] = modality
            frame["fault_type"] = fault_type
            frame["load_level"] = load_level
            frame["severity"] = severity

            frames.append(frame)
            hash_entries.append((rel_path, row_count))
            labels.extend(
                (fault_type, load_level, severity) for _ in range(row_count)
            )

            faults.add(fault_type)  # type: ignore[arg-type]
            loads.add(load_level)  # type: ignore[arg-type]
            severities.add(severity)
            modalities.add(modality)
            availability_columns.update(
                c for c in frame.columns if str(c).endswith("_available")
            )

        if frames:
            X = pd.concat(frames, ignore_index=True, sort=False)
        else:
            X = pd.DataFrame()
    else:
        # Fallback: build a list of row dictionaries when pandas is absent.
        rows: List[Dict] = []
        for rel_path, abs_path, modality in files:
            with open(abs_path, "r", newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                file_rows = list(reader)
            row_count = len(file_rows)
            fault_type, load_level, severity = _parse_filename(rel_path)

            for row in file_rows:
                row["modality"] = modality
                row["fault_type"] = fault_type
                row["load_level"] = load_level
                row["severity"] = severity
                availability_columns.update(
                    k for k in row.keys() if str(k).endswith("_available")
                )

            rows.extend(file_rows)
            hash_entries.append((rel_path, row_count))
            labels.extend(
                (fault_type, load_level, severity) for _ in range(row_count)
            )

            faults.add(fault_type)  # type: ignore[arg-type]
            loads.add(load_level)  # type: ignore[arg-type]
            severities.add(severity)
            modalities.add(modality)

        X = rows  # type: ignore[assignment]

    dataset_hash = _compute_dataset_hash(hash_entries)

    meta = {
        "hash": dataset_hash,
        "files": [rel_path for rel_path, _, _ in files],
        "faults": faults,
        "loads": loads,
        "severities": severities,
        "modalities": modalities,
        "row_count": len(labels),
        "availability_columns": sorted(availability_columns),
    }

    return {"X": X, "y": labels, "meta": meta}


# ============================================================
# 4. MODEL WRAPPER CLASSES
# ============================================================


class TabularModel:
    """Gradient-boosted-tree multiclass classifier (XGBoost/LightGBM).

    Wraps a trained estimator with a uniform ``predict_proba`` / ``predict``
    interface so the inference module and ensemble can treat every model
    family identically (Req 1.2).
    """

    def __init__(self, estimator, label_encoder, feature_names, version):
        self.estimator = estimator
        self.label_encoder = label_encoder
        self.feature_names = feature_names
        self.version = version
        self.family = "tabular"
        self.classes_ = (
            list(label_encoder.classes_) if label_encoder is not None else []
        )

    def _prepare(self, X):
        """Convert X to a numeric matrix aligned to ``feature_names``."""
        if _HAS_PANDAS and isinstance(X, pd.DataFrame):
            return X[self.feature_names].values
        if _HAS_NUMPY and isinstance(X, np.ndarray):
            return X
        # List of dicts or lists
        if _HAS_NUMPY:
            return np.asarray(X, dtype=float)
        return X

    def predict_proba(self, X):
        arr = self._prepare(X)
        if hasattr(self.estimator, "predict_proba"):
            return self.estimator.predict_proba(arr)
        # Fallback: one-hot from predicted labels
        preds = self.estimator.predict(arr)
        return preds

    def predict(self, X):
        arr = self._prepare(X)
        raw = self.estimator.predict(arr)
        if self.label_encoder is not None:
            return self.label_encoder.inverse_transform(raw)
        return raw


class UnsupervisedModel:
    """Isolation-Forest-based anomaly scorer (Req 1.3).

    ``predict`` returns ``"anomaly"`` or ``"normal"`` per sample.
    ``predict_proba`` returns a 2-column array ``[P(normal), P(anomaly)]``
    derived from the decision function so downstream ensembles can combine it.
    """

    def __init__(self, estimator, feature_names, version):
        self.estimator = estimator
        self.feature_names = feature_names
        self.version = version
        self.family = "unsupervised"
        self.classes_ = ["normal", "anomaly"]

    def _prepare(self, X):
        if _HAS_PANDAS and isinstance(X, pd.DataFrame):
            return X[self.feature_names].values
        if _HAS_NUMPY and isinstance(X, np.ndarray):
            return X
        if _HAS_NUMPY:
            return np.asarray(X, dtype=float)
        return X

    def predict(self, X):
        arr = self._prepare(X)
        raw = self.estimator.predict(arr)
        # IsolationForest: 1 = normal, -1 = anomaly
        return ["anomaly" if r == -1 else "normal" for r in raw]

    def predict_proba(self, X):
        arr = self._prepare(X)
        scores = self.estimator.decision_function(arr)
        if _HAS_NUMPY:
            scores = np.asarray(scores)
            # Map decision_function (higher = more normal) to probabilities.
            p_normal = 1.0 / (1.0 + np.exp(-scores))
            p_anomaly = 1.0 - p_normal
            return np.column_stack([p_normal, p_anomaly])
        # Pure-Python fallback
        proba = []
        for s in scores:
            p_n = 1.0 / (1.0 + math.exp(-s))
            proba.append([p_n, 1.0 - p_n])
        return proba


class SequenceModel:
    """LSTM/GRU sequence model over consecutive windows (Req 1.4).

    Uses PyTorch when available.  Falls back to a lightweight markov-like
    baseline when torch is absent so the pipeline never hard-fails.
    """

    def __init__(self, net, feature_names, version, seq_len=5):
        self.net = net
        self.feature_names = feature_names
        self.version = version
        self.family = "sequence"
        self.seq_len = seq_len
        self.classes_ = []

    def predict_proba(self, X):
        if not _HAS_TORCH or self.net is None:
            # Baseline: return uniform distribution
            if _HAS_NUMPY and isinstance(X, np.ndarray):
                n = len(X)
            else:
                n = len(X) if hasattr(X, "__len__") else 1
            if _HAS_NUMPY:
                return np.full((n, max(1, len(self.classes_))), 1.0 / max(1, len(self.classes_)))
            return [[1.0 / max(1, len(self.classes_))] for _ in range(n)]
        arr = _to_numpy(X, self.feature_names)
        self.net.eval()
        with torch.no_grad():
            t = torch.as_tensor(arr, dtype=torch.float32)
            if t.dim() == 2:
                t = t.unsqueeze(0)  # add batch dim
            out = self.net(t)
            return torch.softmax(out, dim=-1).cpu().numpy()

    def predict(self, X):
        proba = self.predict_proba(X)
        if _HAS_NUMPY:
            idx = np.argmax(proba, axis=-1)
        else:
            idx = [max(range(len(p)), key=lambda i: p[i]) for p in proba]
        if self.classes_:
            return [self.classes_[i] for i in idx]
        return idx


class EnsembleModel:
    """Soft-voting ensemble over member models (Req 1.5).

    The combined decision is a deterministic function of member outputs
    (Property 4).  ``predict_proba`` averages member probability vectors,
    aligned by class label.
    """

    def __init__(self, members, version):
        self.members = members  # list of model objects
        self.version = version
        self.family = "ensemble"
        # Union of all member classes, sorted for determinism.
        all_classes = set()
        for m in members:
            all_classes.update(getattr(m, "classes_", []))
        self.classes_ = sorted(all_classes)

    def predict_proba(self, X):
        member_probas = []
        for m in self.members:
            try:
                proba = m.predict_proba(X)
            except Exception:
                continue
            if _HAS_NUMPY and isinstance(proba, np.ndarray):
                proba = proba.tolist()
            member_probas.append((m, proba))

        if not member_probas:
            n = _len_samples(X)
            uniform = 1.0 / max(1, len(self.classes_))
            if _HAS_NUMPY:
                return np.full((n, max(1, len(self.classes_))), uniform)
            return [[uniform] for _ in range(n)]

        n = len(member_probas[0][1])
        # Average aligned probability vectors.
        combined = []
        for sample_idx in range(n):
            class_scores = {c: 0.0 for c in self.classes_}
            count = 0
            for m, proba in member_probas:
                m_classes = getattr(m, "classes_", [])
                if sample_idx < len(proba):
                    row = proba[sample_idx]
                    for j, c in enumerate(m_classes):
                        if c in class_scores and j < len(row):
                            class_scores[c] += row[j]
                    count += 1
            if count:
                for c in class_scores:
                    class_scores[c] /= count
            combined.append([class_scores[c] for c in self.classes_])

        if _HAS_NUMPY:
            return np.asarray(combined)
        return combined

    def predict(self, X):
        proba = self.predict_proba(X)
        if _HAS_NUMPY:
            idx = np.argmax(proba, axis=-1)
        else:
            idx = [max(range(len(p)), key=lambda i: p[i]) for p in proba]
        if self.classes_:
            return [self.classes_[i] for i in idx]
        return idx

    def members_referenced(self):
        """Return the list of member models (Property 4)."""
        return list(self.members)


def _len_samples(X):
    """Return the number of samples in X regardless of type."""
    if _HAS_PANDAS and isinstance(X, pd.DataFrame):
        return len(X)
    if _HAS_NUMPY and isinstance(X, np.ndarray):
        return X.shape[0] if X.ndim >= 1 else 1
    return len(X) if hasattr(X, "__len__") else 1


def _to_numpy(X, feature_names=None):
    """Convert X to a numpy array aligned to feature_names."""
    if _HAS_PANDAS and isinstance(X, pd.DataFrame) and feature_names:
        return X[feature_names].values
    if _HAS_NUMPY and isinstance(X, np.ndarray):
        return X
    if _HAS_NUMPY:
        return np.asarray(X, dtype=float)
    # Pure-Python fallback
    if isinstance(X, list) and X and isinstance(X[0], dict) and feature_names:
        return [[row.get(f, 0.0) for f in feature_names] for row in X]
    return X


# ============================================================
# 5. MINI-BATCH ITERATION  (Requirement 9.2, Property 28)
# ============================================================


def iter_mini_batches(X, batch_size=BATCH_SIZE):
    """Yield successive chunks of X, each of size <= batch_size (Req 9.2).

    Works with numpy arrays, pandas DataFrames, and plain lists.
    """
    if _HAS_PANDAS and isinstance(X, pd.DataFrame):
        n = len(X)
    elif _HAS_NUMPY and isinstance(X, np.ndarray):
        n = X.shape[0]
    elif hasattr(X, "__len__"):
        n = len(X)
    else:
        n = 0
        yield X
        return

    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        yield X[start:end]


# ============================================================
# 6. MODEL TRAINING  (Requirements 1.2-1.5)
# ============================================================


def _feature_columns(X):
    """Return the list of numeric feature column names from X."""
    if _HAS_PANDAS and isinstance(X, pd.DataFrame):
        exclude = {"modality", "fault_type", "load_level", "severity"}
        return [c for c in X.columns if c not in exclude]
    return []


def train_tabular(X, y, version="1.0", config=None):
    """Train a tabular gradient-boosted-tree classifier (Req 1.2).

    Defaults to XGBoost (available).  LightGBM selectable via config when
    installed.  Uses mini-batch training when the dataset exceeds
    ``BATCH_SIZE`` (Req 9.2) and a capacity-reduction fallback on memory
    errors (Req 1.8).
    """
    if not _HAS_XGBOOST:
        raise RuntimeError("XGBoost is required for tabular training but is not installed.")

    config = config or {}
    feature_names = _feature_columns(X)

    label_encoder = LabelEncoder() if _HAS_SKLEARN else None
    y_encoded = label_encoder.fit_transform(y) if label_encoder else y
    n_classes = len(set(y)) if y else 1

    # Memory-fallback estimator config (Req 1.8).
    base_estimators = config.get("n_estimators", 200)
    base_depth = config.get("max_depth", 6)

    try:
        estimator = xgb.XGBClassifier(
            n_estimators=base_estimators,
            max_depth=base_depth,
            objective="multi:softprob" if n_classes > 2 else "binary:logistic",
            num_class=n_classes if n_classes > 2 else None,
            eval_metric="mlogloss" if n_classes > 2 else "logloss",
            use_label_encoder=False,
            tree_method="hist",
            n_jobs=-1,
            random_state=42,
        )

        X_arr = _to_numpy(X, feature_names)
        if _HAS_NUMPY:
            y_arr = np.asarray(y_encoded)
        else:
            y_arr = y_encoded

        # Mini-batch fit when large (Req 9.2).
        if _len_samples(X) > BATCH_SIZE:
            for chunk_X, chunk_y in _zip_mini_batches(X_arr, y_arr, BATCH_SIZE):
                estimator.fit(chunk_X, chunk_y)
        else:
            estimator.fit(X_arr, y_arr)

    except (MemoryError, Exception) as exc:
        if isinstance(exc, MemoryError) or "memory" in str(exc).lower():
            logger.warning("RESOURCE_ERROR: reducing tabular model capacity (%s)", exc)
            estimator = xgb.XGBClassifier(
                n_estimators=max(50, base_estimators // 4),
                max_depth=3,
                tree_method="hist",
                n_jobs=1,
                random_state=42,
            )
            X_arr = _to_numpy(X, feature_names)
            y_arr = np.asarray(y_encoded) if _HAS_NUMPY else y_encoded
            estimator.fit(X_arr, y_arr)
        else:
            raise

    return TabularModel(estimator, label_encoder, feature_names, version)


def train_unsupervised(X, version="1.0", config=None):
    """Train an Isolation-Forest anomaly scorer (Req 1.3).

    Falls back to a simple statistical-distance baseline when sklearn is
    absent.  Uses mini-batching and a capacity-reduction fallback.
    """
    config = config or {}
    feature_names = _feature_columns(X)
    X_arr = _to_numpy(X, feature_names)

    if _HAS_SKLEARN:
        base_estimators = config.get("n_estimators", 100)
        try:
            estimator = IsolationForest(
                n_estimators=base_estimators,
                contamination="auto",
                random_state=42,
                n_jobs=-1,
            )
            estimator.fit(X_arr)
        except (MemoryError, Exception) as exc:
            if isinstance(exc, MemoryError) or "memory" in str(exc).lower():
                logger.warning("RESOURCE_ERROR: reducing unsupervised capacity (%s)", exc)
                estimator = IsolationForest(
                    n_estimators=max(20, base_estimators // 4),
                    contamination="auto",
                    random_state=42,
                    n_jobs=1,
                )
                estimator.fit(X_arr)
            else:
                raise
    else:
        estimator = _StatisticalAnomalyModel(X_arr)

    return UnsupervisedModel(estimator, feature_names, version)


class _StatisticalAnomalyModel:
    """Fallback anomaly model when sklearn is unavailable.

    Uses mean + covariance distance (Mahalanobis-like) to score anomalies.
    """

    def __init__(self, X):
        if _HAS_NUMPY:
            X = np.asarray(X, dtype=float)
            self.mean_ = X.mean(axis=0) if len(X) else np.zeros(1)
            self.std_ = X.std(axis=0) if len(X) else np.ones(1)
            self.std_[self.std_ == 0] = 1.0
        else:
            self.mean_ = []
            self.std_ = []

    def predict(self, X):
        scores = self.decision_function(X)
        return [-1 if s < 0 else 1 for s in scores]

    def decision_function(self, X):
        if _HAS_NUMPY:
            X = np.asarray(X, dtype=float)
            dist = np.abs(X - self.mean_) / self.std_
            return -dist.mean(axis=1)  # higher = more normal
        return [0.0] * len(X)


def train_sequence(X, y=None, version="1.0", config=None):
    """Train an LSTM/GRU sequence model over consecutive windows (Req 1.4).

    Uses PyTorch when available with a small GRU network.  Falls back to a
    baseline that returns uniform probabilities when torch is absent.
    """
    config = config or {}
    feature_names = _feature_columns(X)
    seq_len = config.get("seq_len", 5)
    hidden_size = config.get("hidden_size", 32)
    n_classes = len(set(y)) if y else 2

    net = None
    if _HAS_TORCH:
        X_arr = _to_numpy(X, feature_names)
        if _HAS_NUMPY and len(X_arr) > 0:
            input_size = X_arr.shape[1] if X_arr.ndim > 1 else 1
            try:
                net = _GRUClassifier(input_size, hidden_size, n_classes)
                optimizer = torch.optim.Adam(net.parameters(), lr=1e-3)
                criterion = nn.CrossEntropyLoss()
                epochs = config.get("epochs", 10)

                # Build sliding-window sequences.
                sequences, seq_labels = _make_sequences(X_arr, y, seq_len)
                if len(sequences) > 0:
                    seq_tensor = torch.as_tensor(sequences, dtype=torch.float32)
                    if y and _HAS_SKLEARN:
                        le = LabelEncoder()
                        label_arr = le.fit_transform(y)
                        net.classes_ = list(le.classes_)
                    else:
                        le = None
                    label_tensor = torch.as_tensor(
                        np.asarray(label_arr[:len(sequences)]) if y else np.zeros(len(sequences)),
                        dtype=torch.long,
                    )
                    net.train()
                    for _ in range(epochs):
                        optimizer.zero_grad()
                        out = net(seq_tensor)
                        loss = criterion(out, label_tensor)
                        loss.backward()
                        optimizer.step()
                net.eval()
            except (MemoryError, Exception) as exc:
                if isinstance(exc, MemoryError) or "memory" in str(exc).lower():
                    logger.warning("RESOURCE_ERROR: reducing sequence model capacity (%s)", exc)
                    net = _GRUClassifier(input_size, 8, n_classes)
                else:
                    logger.warning("Sequence model training failed (%s); using baseline", exc)
                    net = None

    model = SequenceModel(net, feature_names, version, seq_len=seq_len)
    model.classes_ = sorted(set(y)) if y else ["normal", "anomaly"]
    return model


class _GRUClassifier(nn.Module if _HAS_TORCH else object):
    """Small GRU classifier for sequence windows."""

    def __init__(self, input_size, hidden_size, n_classes):
        if not _HAS_TORCH:
            return
        super().__init__()
        self.gru = nn.GRU(input_size, hidden_size, batch_first=True)
        self.fc = nn.Linear(hidden_size, n_classes)

    def forward(self, x):
        if not _HAS_TORCH:
            return x
        out, _ = self.gru(x)
        return self.fc(out[:, -1, :])


def _make_sequences(X, y, seq_len):
    """Build sliding-window sequences from X preserving window_index order."""
    n = len(X)
    sequences = []
    seq_labels = []
    for i in range(max(0, n - seq_len + 1)):
        seq = X[i:i + seq_len]
        if len(seq) == seq_len:
            sequences.append(seq)
            if y is not None and i + seq_len - 1 < len(y):
                seq_labels.append(y[i + seq_len - 1])
    if _HAS_NUMPY:
        return np.asarray(sequences), seq_labels
    return sequences, seq_labels


def _zip_mini_batches(X, y, batch_size):
    """Yield (X_chunk, y_chunk) pairs, each <= batch_size."""
    n = len(X)
    for start in range(0, n, batch_size):
        end = min(start + batch_size, n)
        yield X[start:end], y[start:end]


# ============================================================
# 7. VALIDATION AND TRAINING REPORT  (Requirements 1.7, 10)
# ============================================================


def validate_and_report(models, X, y, test_size=0.2):
    """Validate models on a stratified held-out split and emit a report.

    Returns a dict mapping model family -> metrics dict.  Each metrics dict
    carries accuracy, precision, recall, f1, and false_alarm_rate, all in
    [0, 1] (Req 1.7, Property 3).  Accuracy targets gate promotion
    (Req 10.1-10.4).
    """
    feature_names = _feature_columns(X)
    X_arr = _to_numpy(X, feature_names)

    # Encode labels for sklearn metrics.
    if _HAS_SKLEARN and y:
        le = LabelEncoder()
        y_encoded = le.fit_transform(y)
    else:
        y_encoded = y
        le = None

    # Stratified split.
    if _HAS_SKLEARN and len(set(y)) > 1 and len(y) > 4:
        X_train, X_test, y_train, y_test = train_test_split(
            X_arr, y_encoded, test_size=test_size, stratify=y_encoded, random_state=42
        )
    else:
        split_idx = max(1, int(len(y) * (1 - test_size)))
        X_train, X_test = X_arr[:split_idx], X_arr[split_idx:]
        y_train, y_test = y_encoded[:split_idx], y_encoded[split_idx:]

    report = {}
    for name, model in models.items():
        try:
            preds = model.predict(X_test)
            preds_encoded = (
                le.transform(preds) if le and _HAS_SKLEARN else preds
            )
            metrics = _compute_metrics(y_test, preds_encoded)
        except Exception as exc:
            logger.warning("Validation failed for %s: %s", name, exc)
            metrics = {
                "accuracy": 0.0, "precision": 0.0,
                "recall": 0.0, "f1": 0.0, "false_alarm_rate": 1.0,
                "meets_target": False,
            }

        # Promotion gate (Req 10.1-10.4).
        family = getattr(model, "family", name)
        metrics["meets_target"] = _check_promotion_gate(family, metrics)
        report[name] = metrics

    return report


def _compute_metrics(y_true, y_pred):
    """Compute accuracy, precision, recall, F1, and false-alarm rate."""
    if _HAS_SKLEARN and _HAS_NUMPY:
        y_true = np.asarray(y_true)
        y_pred = np.asarray(y_pred)
        avg = "weighted" if len(set(y_true.tolist())) > 2 else "binary"
        try:
            precision = precision_score(y_true, y_pred, average=avg, zero_division=0)
            recall = recall_score(y_true, y_pred, average=avg, zero_division=0)
            f1 = f1_score(y_true, y_pred, average=avg, zero_division=0)
        except Exception:
            precision = recall = f1 = 0.0
        accuracy = accuracy_score(y_true, y_pred)

        # False alarm rate: FP / (FP + TN) for binary; for multiclass use
        # 1 - recall of the normal class.
        try:
            if len(set(y_true.tolist())) <= 2:
                cm = confusion_matrix(y_true, y_pred)
                if cm.shape == (2, 2):
                    fp = cm[0, 1]
                    tn = cm[0, 0]
                    false_alarm = fp / (fp + tn) if (fp + tn) > 0 else 0.0
                else:
                    false_alarm = 1.0 - recall
            else:
                false_alarm = 1.0 - recall
        except Exception:
            false_alarm = 0.0
    else:
        # Pure-Python fallback
        correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
        n = max(1, len(y_true))
        accuracy = correct / n
        precision = recall = f1 = accuracy
        false_alarm = 1.0 - recall

    return {
        "accuracy": round(float(accuracy), 4),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "false_alarm_rate": round(float(false_alarm), 4),
    }


def _check_promotion_gate(family, metrics):
    """Check whether a model meets its accuracy target (Req 10.1-10.4)."""
    if family == "tabular":
        return metrics["accuracy"] >= TABULAR_ACCURACY_TARGET
    if family == "unsupervised":
        return (
            metrics["f1"] >= UNSUPERVISED_F1_TARGET
            and metrics["false_alarm_rate"] <= FALSE_ALARM_RATE_MAX
        )
    if family == "ensemble":
        return metrics["accuracy"] >= TABULAR_ACCURACY_TARGET
    # sequence, explorer, etc.
    return metrics["f1"] >= UNSUPERVISED_F1_TARGET


# ============================================================
# 8. MODEL PERSISTENCE  (Requirement 1.6)
# ============================================================


def persist_model(model, family, out_dir, dataset_hash, metrics=None, version=None):
    """Persist a model artifact to disk with a manifest.json (Req 1.6).

    Writes the pickled model and a manifest carrying ``version``,
    ``training_timestamp``, ``dataset_hash``, and metrics under
    ``{out_dir}/{family}/{version}/``.  Returns the manifest dict.
    """
    version = version or getattr(model, "version", "1.0")
    artifact_dir = os.path.join(out_dir, family, version)
    os.makedirs(artifact_dir, exist_ok=True)

    manifest = {
        "family": family,
        "model_name": type(model).__name__,
        "version": version,
        "training_timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset_hash": dataset_hash,
        "artifact_path": artifact_dir,
        "metrics": metrics or {},
        "schema_version": "1.0",
    }

    # Pickle the model object.
    model_path = os.path.join(artifact_dir, "model.pkl")
    try:
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
    except Exception as exc:
        logger.warning("Could not pickle %s model: %s", family, exc)

    # Write the manifest.
    manifest_path = os.path.join(artifact_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)

    return manifest


def load_model_artifact(family, version, out_dir):
    """Reload a persisted model artifact and its manifest (Req 1.6).

    Returns ``(model, manifest)`` or ``(None, None)`` if not found.
    """
    artifact_dir = os.path.join(out_dir, family, version)
    manifest_path = os.path.join(artifact_dir, "manifest.json")
    model_path = os.path.join(artifact_dir, "model.pkl")

    if not os.path.exists(manifest_path):
        return None, None

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    model = None
    if os.path.exists(model_path):
        try:
            with open(model_path, "rb") as f:
                model = pickle.load(f)
        except Exception as exc:
            logger.warning("Could not unpickle %s/%s: %s", family, version, exc)

    return model, manifest


# ============================================================
# 9. FULL TRAINING PIPELINE  (Requirements 1, 9, 10)
# ============================================================


def run_training(dataset_root="KAIST/features/batch", out_dir="Backend/models"):
    """Run the full training pipeline: load, train, validate, persist, report.

    Orchestrates the complete offline workflow (design §4):
    1. Load the unified training set (Req 1.1).
    2. Train tabular, unsupervised, sequence, and ensemble models (Req 1.2-1.5).
    3. Validate and emit a report with per-model metrics (Req 1.7).
    4. Persist artifacts with manifests (Req 1.6).
    5. Register active models with the model registry.

    Returns the training report dict.
    """
    unified = load_unified_training_set(dataset_root)
    X, y, meta = unified["X"], unified["y"], unified["meta"]
    dataset_hash = meta["hash"]

    if not y:
        logger.warning("Empty training set; skipping model training.")
        return {"error": "empty training set", "meta": meta}

    # Generate version string from timestamp.
    version = datetime.now(timezone.utc).strftime("v%Y%m%d_%H%M%S")

    # Train model families (Req 1.2-1.5).
    models = {}
    try:
        models["tabular"] = train_tabular(X, y, version=version)
    except Exception as exc:
        logger.error("Tabular training failed: %s", exc)

    try:
        models["unsupervised"] = train_unsupervised(X, version=version)
    except Exception as exc:
        logger.error("Unsupervised training failed: %s", exc)

    try:
        models["sequence"] = train_sequence(X, y, version=version)
    except Exception as exc:
        logger.error("Sequence training failed: %s", exc)

    # Ensemble over available members (Req 1.5).
    if models:
        ensemble = EnsembleModel(list(models.values()), version=version)
        models["ensemble"] = ensemble
    else:
        logger.error("No models trained successfully.")
        return {"error": "no models trained", "meta": meta}

    # Validate and report (Req 1.7).
    report = validate_and_report(models, X, y)

    # Persist and register models that meet their targets (Req 1.6, 10.4).
    out_dir_abs = os.path.abspath(out_dir)
    for name, model in models.items():
        metrics = report.get(name, {})
        manifest = persist_model(
            model, name, out_dir_abs, dataset_hash,
            metrics=metrics, version=version,
        )

        # Register with the model registry and activate if it meets target.
        try:
            from model_registry import registry
            registry.register(
                model, family=name, version=version,
                metrics=metrics, dataset_hash=dataset_hash,
                artifact_path=manifest["artifact_path"],
            )
            if metrics.get("meets_target", False):
                registry.set_active(name, version)
                logger.info("Activated %s model %s (meets target)", name, version)
            else:
                logger.info(
                    "%s model %s did not meet target: %s",
                    name, version, metrics,
                )
        except Exception as exc:
            logger.warning("Registry registration failed for %s: %s", name, exc)

    report["dataset_hash"] = dataset_hash
    report["version"] = version
    report["meta"] = meta
    return report


# ============================================================
# 10. SUMMARY / SELF-TEST ENTRYPOINT
# ============================================================


def _print_summary(unified: Dict) -> None:
    """Print human-readable summary statistics for a unified training set."""
    meta = unified["meta"]
    y = unified["y"]
    X = unified["X"]

    print("=" * 65)
    print("INTELLIWATCH - UNIFIED TRAINING SET SUMMARY")
    print("=" * 65)

    print(f"Dataset root hash : {meta['hash']}")
    print(f"Files loaded      : {len(meta['files'])}")
    print(f"Total windows     : {meta['row_count']}")
    print(f"Fault types       : {sorted(meta['faults'])}")
    print(f"Load levels       : {sorted(meta['loads'])}")
    print(f"Severities        : {sorted(s for s in meta['severities'] if s)}")
    print(f"Modalities        : {sorted(meta['modalities'])}")
    print(f"Availability cols : {meta['availability_columns']}")

    if y:
        # Per (fault, load) window counts.
        counts: Dict[Tuple[str, str], int] = {}
        for fault_type, load_level, _severity in y:
            key = (str(fault_type), str(load_level))
            counts[key] = counts.get(key, 0) + 1
        print("\n(fault, load) coverage:")
        for key in sorted(counts):
            print(f"  {key[0]:<12} {key[1]:<5} -> {counts[key]} windows")

    if _HAS_PANDAS and isinstance(X, pd.DataFrame) and not X.empty:
        print(f"\nFeature frame shape: {X.shape}")
        print(f"Feature frame columns ({len(X.columns)}): "
              f"{list(X.columns)}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Resolve the default dataset location relative to this file so the demo
    # works no matter which directory it is launched from. The module lives in
    # ``Backend/`` and the KAIST dataset sits at the repository root.
    _default_root = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "KAIST", "features", "batch")
    )
    _unified = load_unified_training_set(_default_root)
    _print_summary(_unified)
