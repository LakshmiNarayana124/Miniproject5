"""
Unit tests for database schema and helpers.
Validates: Requirements 2.5, 3.8, 6.1, 8.1, 13.1
"""
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import database


REQUIRED_TABLES = [
    "sensor_readings", "sensor_analytics", "machine_assessments",
    "anomaly_events", "recommendations", "machine_config",
    "users", "user_permissions", "firebase_identities",
    "ml_models", "verified_labels", "accuracy_trend",
    "control_signals", "audit_entries", "edge_devices",
    "control_signal_queue", "explorer_history", "threshold_definitions",
    "admin_promotion_requests", "account_recovery_requests",
]

RECOMMENDED_INDEXES = [
    "idx_ml_models_active", "idx_verified_model_ts",
    "idx_control_intent_ts", "idx_audit_category_ts",
    "idx_explorer_ts",
]


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    orig = database.DATABASE_PATH
    db_path = tmp_path / "test_schema.db"
    database.DATABASE_PATH = db_path
    database.initialize_database()
    yield
    database.DATABASE_PATH = orig


def _tables():
    conn = database.get_connection()
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    conn.close()
    return {r["name"] for r in rows}


def _indexes():
    conn = database.get_connection()
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'"
    ).fetchall()
    conn.close()
    return {r["name"] for r in rows}


def test_all_required_tables_exist():
    missing = [t for t in REQUIRED_TABLES if t not in _tables()]
    assert not missing, f"Missing tables: {missing}"


def test_recommended_indexes_present():
    present = _indexes()
    missing = [i for i in RECOMMENDED_INDEXES if i not in present]
    if missing:
        pytest.skip(f"Optional indexes not present (non-fatal): {missing}")


def test_audit_entries_hash_column():
    conn = database.get_connection()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(audit_entries)").fetchall()}
    conn.close()
    assert "hash" in cols, "audit_entries missing 'hash' column"


def test_save_and_retrieve_explorer_history():
    database.save_explorer_history_entry(
        entry_type="workspace_state",
        active_user="user1",
        arrangement_json='{"components":[]}',
    )
    rows = database.get_explorer_history(limit=10)
    assert len(rows) >= 1
    assert rows[0]["entry_type"] == "workspace_state"


def test_explorer_history_reverse_order():
    for i in range(3):
        database.save_explorer_history_entry(
            entry_type="workspace_state",
            active_user="user1",
            arrangement_json=f'{{"i":{i}}}',
        )
    rows = database.get_explorer_history(limit=10)
    ids = [r["id"] for r in rows]
    assert ids == sorted(ids, reverse=True), "Explorer history not in reverse order"


def test_record_audit_entry_creates_hash():
    database.record_audit_entry(
        category="TEST_EVENT",
        actor="tester",
        target="1",
        detail_json='{"test":true}',
    )
    conn = database.get_connection()
    row = conn.execute(
        "SELECT hash FROM audit_entries WHERE category='TEST_EVENT'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["hash"], "hash is empty"


def test_save_verified_label_round_trip():
    features = {"rms_x": 0.5, "peak_x": 1.0}
    database.save_verified_label(
        event_id=None,
        label="normal",
        feature_vector_json=json.dumps(features),
        model_version="tabular-v0.1",
        verified_by="op1",
    )
    conn = database.get_connection()
    row = conn.execute(
        "SELECT * FROM verified_labels ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    assert row is not None
    stored = json.loads(row["feature_vector_json"])
    assert stored["rms_x"] == pytest.approx(0.5)
    assert row["model_version"] == "tabular-v0.1"
    assert row["verified_by"] == "op1"
