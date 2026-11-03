"""
INTELLIWATCH - DATABASE HELPER TEST SUITE

Verifies the AIML persistence helpers added for the new tables
(ml_models, verified_labels, accuracy_trend, control_signals,
audit_entries, edge_devices, control_signal_queue, explorer_history).

Uses an isolated temporary SQLite database by redirecting the module
level DATABASE_PATH, mirroring the style of test_engine.py.
"""

import unittest
import tempfile
import sqlite3
import json

from pathlib import Path
from contextlib import closing

import database


class TestDatabaseHelpers(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            ignore_cleanup_errors=True
        )

        self.db_path = (
            Path(self.temp_dir.name) / "test_helpers.db"
        )

        # Redirect the module-level database path to the temp file.
        self._original_db_path = database.DATABASE_PATH
        database.DATABASE_PATH = self.db_path

        database.initialize_database()

    def tearDown(self):
        database.DATABASE_PATH = self._original_db_path
        self.temp_dir.cleanup()

    # -----------------------------------------
    # Helper: run raw SQL against the temp db
    # -----------------------------------------

    def fetch_one(self, query, params=()):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(query, params).fetchone()

    def fetch_all(self, query, params=()):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(query, params).fetchall()

    def insert_control_signal(self, intent="SHUTDOWN", priority=10):
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.execute("""
                INSERT INTO control_signals (
                    timestamp, intent, system_status, priority
                )
                VALUES (?, ?, ?, ?)
            """, (
                database.current_timestamp(),
                intent,
                "CRITICAL",
                priority
            ))
            conn.commit()
            return cursor.lastrowid

    def insert_anomaly_event(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.execute("""
                INSERT INTO anomaly_events (
                    timestamp, sensor_name, severity
                )
                VALUES (?, ?, ?)
            """, (
                database.current_timestamp(),
                "Vibration Sensor",
                "WARNING"
            ))
            conn.commit()
            return cursor.lastrowid

    def insert_ml_model(self, version="v1"):
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.execute("""
                INSERT INTO ml_models (
                    family, model_name, version, training_timestamp,
                    dataset_hash, artifact_path
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                "tabular", "lightgbm", version,
                database.current_timestamp(), "hash123", "/tmp/model"
            ))
            conn.commit()
            return cursor.lastrowid

    # -----------------------------------------
    # save_control_ack
    # -----------------------------------------

    def test_save_control_ack_updates_row(self):
        signal_id = self.insert_control_signal()

        ack_ts = database.current_timestamp()
        updated = database.save_control_ack(
            signal_id, ack_ts, "OFFLINE"
        )

        self.assertTrue(updated)

        row = self.fetch_one(
            "SELECT ack_timestamp, resulting_equipment_state "
            "FROM control_signals WHERE id = ?",
            (signal_id,)
        )

        self.assertEqual(row["ack_timestamp"], ack_ts)
        self.assertEqual(row["resulting_equipment_state"], "OFFLINE")

    def test_save_control_ack_missing_row_returns_false(self):
        updated = database.save_control_ack(999999, "ts", "OFFLINE")
        self.assertFalse(updated)

    # -----------------------------------------
    # record_audit_entry (chain hash)
    # -----------------------------------------

    def test_record_audit_entry_inserts_with_chain_hash(self):
        first_id = database.record_audit_entry(
            "control_dispatch",
            json.dumps({"intent": "SHUTDOWN"}),
            actor="admin",
            target="pump-1"
        )

        second_id = database.record_audit_entry(
            "model_promotion",
            json.dumps({"version": "v2"}),
            actor="admin"
        )

        self.assertGreater(first_id, 0)
        self.assertGreater(second_id, first_id)

        rows = self.fetch_all("SELECT * FROM audit_entries ORDER BY id")

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["category"], "control_dispatch")
        self.assertEqual(rows[0]["actor"], "admin")
        self.assertEqual(rows[0]["target"], "pump-1")
        # Every audit entry must carry a non-empty hash.
        self.assertTrue(rows[0]["hash"])
        self.assertTrue(rows[1]["hash"])
        # Chain hashes of distinct entries must differ.
        self.assertNotEqual(rows[0]["hash"], rows[1]["hash"])

    def test_record_audit_entry_explicit_hash_is_used(self):
        explicit = "deadbeef"
        entry_id = database.record_audit_entry(
            "recalibration",
            json.dumps({"f1": 0.93}),
            hash_value=explicit
        )

        row = self.fetch_one(
            "SELECT hash FROM audit_entries WHERE id = ?",
            (entry_id,)
        )

        self.assertEqual(row["hash"], explicit)

    # -----------------------------------------
    # save_verified_label
    # -----------------------------------------

    def test_save_verified_label_round_trip(self):
        event_id = self.insert_anomaly_event()
        fv = json.dumps([0.1, 0.2, 0.3])

        label_id = database.save_verified_label(
            event_id, "confirm", fv, "v1", "operator1"
        )

        self.assertGreater(label_id, 0)

        row = self.fetch_one(
            "SELECT * FROM verified_labels WHERE id = ?",
            (label_id,)
        )

        self.assertEqual(row["event_id"], event_id)
        self.assertEqual(row["label"], "confirm")
        self.assertEqual(row["feature_vector_json"], fv)
        self.assertEqual(row["model_version"], "v1")
        self.assertEqual(row["verified_by"], "operator1")
        self.assertTrue(row["verified_at"])

    # -----------------------------------------
    # append_accuracy_trend
    # -----------------------------------------

    def test_append_accuracy_trend_round_trip(self):
        model_id = self.insert_ml_model()

        trend_id = database.append_accuracy_trend(model_id, 0.94)

        self.assertGreater(trend_id, 0)

        row = self.fetch_one(
            "SELECT * FROM accuracy_trend WHERE id = ?",
            (trend_id,)
        )

        self.assertEqual(row["model_id"], model_id)
        self.assertAlmostEqual(row["f1_score"], 0.94)
        self.assertTrue(row["measured_at"])

    # -----------------------------------------
    # save_explorer_history_entry / get_explorer_history
    # -----------------------------------------

    def test_save_and_get_explorer_history(self):
        ws_id = database.save_explorer_history_entry(
            "workspace_state",
            active_user="alice",
            arrangement_json=json.dumps({"parts": ["a", "b"]})
        )

        cls_id = database.save_explorer_history_entry(
            "classification",
            classification_label="anomalous",
            confidence=0.88,
            model_version="explorer-v1"
        )

        self.assertGreater(ws_id, 0)
        self.assertGreater(cls_id, ws_id)

        history = database.get_explorer_history(limit=10)

        # Reverse-chronological: classification is newest.
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["id"], cls_id)
        self.assertEqual(history[0]["entry_type"], "classification")
        self.assertEqual(history[0]["classification_label"], "anomalous")
        self.assertAlmostEqual(history[0]["confidence"], 0.88)
        self.assertEqual(history[1]["id"], ws_id)
        self.assertEqual(history[1]["entry_type"], "workspace_state")
        self.assertEqual(history[1]["active_user"], "alice")

    def test_get_explorer_history_entry_single(self):
        entry_id = database.save_explorer_history_entry(
            "classification",
            classification_label="normal",
            confidence=0.5,
            model_version="explorer-v1"
        )

        entry = database.get_explorer_history_entry(entry_id)

        self.assertIsNotNone(entry)
        self.assertEqual(entry["id"], entry_id)
        self.assertEqual(entry["classification_label"], "normal")

    def test_get_explorer_history_entry_missing_returns_none(self):
        self.assertIsNone(database.get_explorer_history_entry(999999))

    # -----------------------------------------
    # save_edge_device / update_edge_device_status
    # -----------------------------------------

    def test_save_edge_device_insert_then_upsert(self):
        database.save_edge_device("dev-1", "MQTT", status="online")

        rows = self.fetch_all(
            "SELECT * FROM edge_devices WHERE device_id = ?",
            ("dev-1",)
        )
        self.assertEqual(len(rows), 1)
        original_registered = rows[0]["registered_at"]
        self.assertEqual(rows[0]["protocol"], "MQTT")
        self.assertEqual(rows[0]["status"], "online")

        # Upsert updates protocol/status but keeps registered_at.
        database.save_edge_device("dev-1", "HTTP", status="offline")

        rows = self.fetch_all(
            "SELECT * FROM edge_devices WHERE device_id = ?",
            ("dev-1",)
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["protocol"], "HTTP")
        self.assertEqual(rows[0]["status"], "offline")
        self.assertEqual(rows[0]["registered_at"], original_registered)

    def test_update_edge_device_status(self):
        database.save_edge_device("dev-2", "MQTT")

        updated = database.update_edge_device_status(
            "dev-2", "unresponsive",
            last_known_state_json=json.dumps({"temp": 80})
        )

        self.assertTrue(updated)

        row = self.fetch_one(
            "SELECT status, last_known_state_json "
            "FROM edge_devices WHERE device_id = ?",
            ("dev-2",)
        )

        self.assertEqual(row["status"], "unresponsive")
        self.assertEqual(
            json.loads(row["last_known_state_json"])["temp"], 80
        )

    def test_update_edge_device_status_missing_returns_false(self):
        updated = database.update_edge_device_status("ghost", "offline")
        self.assertFalse(updated)

    # -----------------------------------------
    # queue_control_signal / get_queued_signals / mark_signal_delivered
    # -----------------------------------------

    def test_queue_and_deliver_signals(self):
        database.save_edge_device("dev-3", "MQTT")

        low_id = database.queue_control_signal("dev-3", "RUN", 1)
        high_id = database.queue_control_signal("dev-3", "SHUTDOWN", 10)

        self.assertGreater(low_id, 0)
        self.assertGreater(high_id, low_id)

        queued = database.get_queued_signals("dev-3")

        # Highest priority (SHUTDOWN, prio 10) comes first.
        self.assertEqual(len(queued), 2)
        self.assertEqual(queued[0]["id"], high_id)
        self.assertEqual(queued[0]["intent"], "SHUTDOWN")
        self.assertEqual(queued[1]["id"], low_id)
        self.assertEqual(queued[1]["intent"], "RUN")
        self.assertTrue(all(q["delivered_at"] is None for q in queued))

        # Mark the high-priority signal as delivered.
        delivered = database.mark_signal_delivered(high_id)
        self.assertTrue(delivered)

        # undelivered_only should now return just the low-priority signal.
        remaining = database.get_queued_signals("dev-3")
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0]["id"], low_id)

        # Full list includes the delivered one too.
        all_signals = database.get_queued_signals(
            "dev-3", undelivered_only=False
        )
        self.assertEqual(len(all_signals), 2)

    def test_mark_signal_delivered_missing_returns_false(self):
        self.assertFalse(database.mark_signal_delivered(999999))


if __name__ == "__main__":
    unittest.main(verbosity=2)
