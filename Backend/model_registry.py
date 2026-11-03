"""
INTELLIWATCH - MODEL REGISTRY
Version: 1.0

Purpose:
- In-memory + on-disk catalog of trained anomaly-detection models.
- Thread-safe registration, activation, and lookup keyed by
  family and version.
- Exactly one active model version per family (ensemble by default).
- SQLite persistence via the ``ml_models`` table.
- On-disk manifests under ``Backend/models/{family}/{version}/manifest.json``.

Dependencies:
- Python standard library.
- Existing ``database.py`` (``get_connection``).
"""

import json
import threading

from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional

import database


# =====================================================
# CONFIGURATION
# =====================================================

BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"

SCHEMA_VERSION = "1.0"

DEFAULT_FAMILY = "ensemble"


def _current_timestamp() -> str:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc).isoformat()


# =====================================================
# MODEL REGISTRY
# =====================================================

class ModelRegistry:
    """
    Thread-safe in-memory + on-disk catalog of trained models.

    Each model is keyed by ``(family, version)``. Only one version
    per family may be active at a time. Registering a model writes a
    ``manifest.json`` to disk and upserts a row in the ``ml_models``
    table, then keeps the live model object in memory so the in-process
    inference path can use it without IPC overhead.
    """

    def __init__(self, models_dir: Optional[Path] = None) -> None:
        self._models_dir = Path(models_dir or MODELS_DIR)
        self._models_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()

        # (family, version) -> catalog entry holding the model object
        # and its manifest metadata.
        self._catalog: dict[tuple[str, str], dict[str, Any]] = {}

        # family -> currently active version.
        self._active: dict[str, str] = {}

    # -------------------------------------------------
    # REGISTER
    # -------------------------------------------------

    def register(
        self,
        model: Any,
        family: str,
        version: str,
        metrics: Optional[dict[str, Any]] = None,
        dataset_hash: Optional[str] = None,
        artifact_path: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Register a trained model in the in-memory catalog, write its
        manifest to disk, and upsert a row in the ``ml_models`` table.

        The model is registered inactive; call ``set_active`` to make it
        the live model for its family.

        Returns the manifest dictionary that was persisted.
        """

        family = str(family).strip()
        version = str(version).strip()

        if not family or not version:
            raise ValueError("family and version are required.")

        dataset_hash = dataset_hash or ""
        metrics = metrics or {}
        model_name = type(model).__name__

        # Resolve the on-disk artifact directory.
        artifact_dir = self._models_dir / family / version
        artifact_dir.mkdir(parents=True, exist_ok=True)

        artifact_path = str(artifact_path) if artifact_path else str(artifact_dir)

        training_timestamp = _current_timestamp()

        manifest = {
            "family": family,
            "model_name": model_name,
            "version": version,
            "training_timestamp": training_timestamp,
            "dataset_hash": dataset_hash,
            "artifact_path": artifact_path,
            "metrics": metrics,
            "schema_version": SCHEMA_VERSION
        }

        # 1. Write the manifest to disk.
        manifest_path = artifact_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, default=str),
            encoding="utf-8"
        )

        # 2. Persist to the database.
        self._upsert_model_row(
            family=family,
            model_name=model_name,
            version=version,
            training_timestamp=training_timestamp,
            dataset_hash=dataset_hash,
            artifact_path=artifact_path,
            metrics=metrics
        )

        # 3. Store in the in-memory catalog (thread-safe).
        entry = {
            "model": model,
            "manifest": manifest,
            "is_active": self._active.get(family) == version
        }

        with self._lock:
            self._catalog[(family, version)] = entry

        return manifest

    # -------------------------------------------------
    # SET ACTIVE
    # -------------------------------------------------

    def set_active(self, family: str, version: str) -> bool:
        """
        Mark ``version`` as the active model for ``family``.

        Exactly one version per family is active at a time, so every
        other version in the family is deactivated first. The change is
        persisted to the ``ml_models`` table and mirrored in the
        in-memory catalog.

        Returns ``True`` if a matching registered model was found,
        otherwise ``False``.
        """

        family = str(family).strip()
        version = str(version).strip()

        if not family or not version:
            raise ValueError("family and version are required.")

        with self._lock:
            # The model must be registered (in memory or database).
            if (family, version) not in self._catalog:
                if not self._model_row_exists(family, version):
                    return False

            # Deactivate every other version in this family.
            self._deactivate_family_rows(family)

            # Activate the selected version.
            self._activate_model_row(family, version)

            # Mirror the active state in memory.
            self._active[family] = version

            for key, entry in self._catalog.items():
                if key[0] == family:
                    entry["is_active"] = (key[1] == version)

        return True

    # -------------------------------------------------
    # ACTIVE MODEL
    # -------------------------------------------------

    def active_model(self, family: str = DEFAULT_FAMILY) -> Any:
        """
        Return the currently active model object for ``family``,
        or ``None`` when no model is active or the model object has not
        been loaded into memory.
        """

        family = str(family).strip()

        with self._lock:
            version = self._active.get(family)

            if version is None:
                version = self._active_version_from_db(family)

                if version is None:
                    return None

                self._active[family] = version

            entry = self._catalog.get((family, version))

        if entry is None:
            return None

        return entry["model"]

    # -------------------------------------------------
    # GET MANIFEST
    # -------------------------------------------------

    def get_manifest(
        self,
        family: str,
        version: str
    ) -> Optional[dict[str, Any]]:
        """
        Return the manifest for ``(family, version)``.

        The manifest is read from the in-memory catalog when available,
        otherwise it is loaded from the on-disk ``manifest.json``.
        Returns ``None`` when the model is not registered.
        """

        family = str(family).strip()
        version = str(version).strip()

        with self._lock:
            entry = self._catalog.get((family, version))

        if entry is not None:
            return dict(entry["manifest"])

        # Fall back to the on-disk manifest.
        manifest_path = (
            self._models_dir / family / version / "manifest.json"
        )

        if manifest_path.exists():
            return json.loads(
                manifest_path.read_text(encoding="utf-8")
            )

        return None

    # -------------------------------------------------
    # LIST MODELS
    # -------------------------------------------------

    def list_models(
        self,
        family: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """
        List registered models.

        When ``family`` is given, only models in that family are
        returned. Each item carries the manifest metadata and the
        active flag, but never the model object itself.
        """

        family = str(family).strip() if family else None

        with self._lock:
            entries = list(self._catalog.items())

        results: list[dict[str, Any]] = []

        for (model_family, model_version), entry in entries:
            if family and model_family != family:
                continue

            manifest = dict(entry["manifest"])
            manifest["is_active"] = entry["is_active"]
            results.append(manifest)

        return results

    # =====================================================
    # DATABASE HELPERS
    # =====================================================

    def _upsert_model_row(
        self,
        family: str,
        model_name: str,
        version: str,
        training_timestamp: str,
        dataset_hash: str,
        artifact_path: str,
        metrics: dict[str, Any]
    ) -> None:
        """Insert or update a ``ml_models`` row for the model."""

        connection = database.get_connection()

        try:
            connection.execute("""
                INSERT INTO ml_models (
                    family,
                    model_name,
                    version,
                    is_active,
                    training_timestamp,
                    dataset_hash,
                    artifact_path,
                    metrics_json,
                    schema_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(family, version)
                DO UPDATE SET
                    model_name = excluded.model_name,
                    training_timestamp = excluded.training_timestamp,
                    dataset_hash = excluded.dataset_hash,
                    artifact_path = excluded.artifact_path,
                    metrics_json = excluded.metrics_json,
                    schema_version = excluded.schema_version
            """, (
                family,
                model_name,
                version,
                0,
                training_timestamp,
                dataset_hash,
                artifact_path,
                json.dumps(metrics, default=str),
                SCHEMA_VERSION
            ))

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def _model_row_exists(self, family: str, version: str) -> bool:
        """Return ``True`` when a matching ``ml_models`` row exists."""

        connection = database.get_connection()

        try:
            row = connection.execute("""
                SELECT 1
                FROM ml_models
                WHERE family = ? AND version = ?
            """, (family, version)).fetchone()

            return row is not None

        finally:
            connection.close()

    def _deactivate_family_rows(self, family: str) -> None:
        """Set ``is_active = 0`` for every version in ``family``."""

        connection = database.get_connection()

        try:
            connection.execute("""
                UPDATE ml_models
                SET is_active = 0
                WHERE family = ?
            """, (family,))

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def _activate_model_row(self, family: str, version: str) -> None:
        """Set ``is_active = 1`` for the selected ``(family, version)``."""

        connection = database.get_connection()

        try:
            connection.execute("""
                UPDATE ml_models
                SET is_active = 1
                WHERE family = ? AND version = ?
            """, (family, version))

            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def _active_version_from_db(self, family: str) -> Optional[str]:
        """Return the active version for ``family`` from the database."""

        connection = database.get_connection()

        try:
            row = connection.execute("""
                SELECT version
                FROM ml_models
                WHERE family = ? AND is_active = 1
                LIMIT 1
            """, (family,)).fetchone()

            return row["version"] if row else None

        finally:
            connection.close()


# =====================================================
# MODULE-LEVEL SINGLETON
# =====================================================

registry = ModelRegistry()
