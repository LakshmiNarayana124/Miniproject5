"""
INTELLIWATCH - LEARNING SYSTEM
Adaptive learning loop: ingest operator labels, recalibrate, promote.
Requirements: 8.1-8.5, 10.1-10.4, 13.2
"""

import json
import logging
from datetime import datetime, timezone

import database
import model_registry as _mr

logger = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc).isoformat()


class LearningSystem:
    """Accept operator labels and recalibrate/promote models (Req 8.1-8.5)."""

    def __init__(self, registry=None):
        self.registry = registry or _mr.registry

    # --------------------------------------------------------
    # 10.1 — submit_label  (Req 8.1, 8.2)
    # --------------------------------------------------------
    def submit_label(self, event_id, label, feature_vector, model_version, verified_by):
        """Store an operator-verified label with its feature vector (Req 8.1, 8.2)."""
        fv_json = json.dumps(feature_vector, default=str) if not isinstance(feature_vector, str) else feature_vector
        row_id = database.save_verified_label(
            event_id=event_id,
            label=label,
            feature_vector_json=fv_json,
            model_version=model_version,
            verified_by=verified_by,
        )
        # Log for event-log completeness (Req 14.3)
        database.record_audit_entry(
            category="feedback_ingestion",
            detail_json=json.dumps({"event_id": event_id, "label": label, "model_version": model_version}),
            actor=verified_by,
        )
        return row_id

    # --------------------------------------------------------
    # 10.3 — recalibrate  (Req 8.3-8.5, 13.2)
    # --------------------------------------------------------
    def recalibrate(self, family="tabular"):
        """Train a candidate from accumulated labels and promote if better (Req 8.3-8.5)."""
        # Load accumulated verified labels
        labels_rows = self._load_labels()
        if not labels_rows:
            logger.info("No verified labels available for recalibration.")
            return {"promoted": False, "reason": "no labels"}

        # Build feature matrix from stored vectors
        try:
            X, y = self._build_dataset(labels_rows)
        except Exception as exc:
            logger.warning("Could not build dataset for recalibration: %s", exc)
            return {"promoted": False, "reason": str(exc)}

        # Train a candidate (Req 8.3)
        try:
            from training_pipeline import train_tabular, validate_and_report, persist_model, _check_promotion_gate
            import pandas as pd
            candidate = train_tabular(X, y, version=_now()[:19].replace(":", "").replace("-", "").replace("T", "_"))
        except Exception as exc:
            logger.warning("Recalibration training failed: %s", exc)
            return {"promoted": False, "reason": str(exc)}

        # Validate candidate
        try:
            report = validate_and_report({"tabular": candidate}, X, y)
            metrics = report.get("tabular", {})
        except Exception as exc:
            metrics = {"f1": 0.0, "accuracy": 0.0, "meets_target": False}

        candidate_f1 = metrics.get("f1", 0.0)

        # Get active model's F1 for comparison (Req 8.4)
        active_model = self.registry.active_model(family)
        active_f1 = 0.0
        if active_model is not None:
            active_manifest = self.registry.get_manifest(family, getattr(active_model, "version", ""))
            if active_manifest:
                active_f1 = active_manifest.get("metrics", {}).get("f1", 0.0)

        promoted = False
        gate_passed = _check_promotion_gate("tabular", metrics)

        if gate_passed and candidate_f1 > active_f1:
            # Promote (Req 8.4)
            try:
                import os
                out_dir = os.path.join(os.path.dirname(__file__), "models")
                persist_model(candidate, family, out_dir, dataset_hash="recalibration", metrics=metrics)
                self.registry.register(candidate, family=family, version=candidate.version, metrics=metrics)
                self.registry.set_active(family, candidate.version)
                promoted = True
            except Exception as exc:
                logger.warning("Promotion failed: %s", exc)

        # Append accuracy trend (Req 8.5)
        try:
            self._append_trend(family, candidate.version, candidate_f1)
        except Exception as exc:
            logger.warning("Could not append accuracy trend: %s", exc)

        # Audit entry (Req 13.2)
        action = "model_promotion" if promoted else "recalibration"
        database.record_audit_entry(
            category=action,
            detail_json=json.dumps({
                "family": family,
                "version": getattr(candidate, "version", "?"),
                "metrics": metrics,
                "promoted": promoted,
                "candidate_f1": candidate_f1,
                "active_f1": active_f1,
            }),
        )

        return {"promoted": promoted, "metrics": metrics, "candidate_f1": candidate_f1}

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------
    def _load_labels(self):
        conn = database.get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM verified_labels ORDER BY verified_at ASC"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def _build_dataset(self, rows):
        """Return (X, y) from stored verified_labels rows."""
        try:
            import pandas as pd
            records = []
            labels = []
            for row in rows:
                fv = json.loads(row["feature_vector_json"])
                if isinstance(fv, dict):
                    records.append(fv)
                elif isinstance(fv, list):
                    records.append({f"f{i}": v for i, v in enumerate(fv)})
                labels.append(row["label"])
            X = pd.DataFrame(records).fillna(0.0)
            return X, labels
        except Exception:
            raise

    def _append_trend(self, family, version, f1):
        conn = database.get_connection()
        try:
            row = conn.execute(
                "SELECT id FROM ml_models WHERE family=? AND version=?",
                (family, version)
            ).fetchone()
            if row:
                database.append_accuracy_trend(row["id"], f1)
        finally:
            conn.close()
