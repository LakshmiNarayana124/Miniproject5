"""
Property 21: Explorer history persistence round-trip
Validates: Requirements 6.1, 6.2

workspace_state and classification entries survive a save/load round-trip.
"""
import os
import sys
import json
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    import database
    _HAS_DB = True
except ImportError:
    _HAS_DB = False


def _setup(tmp_dir):
    database.DATABASE_PATH = os.path.join(tmp_dir, "test_exh.db")
    database.initialize_database()


@pytest.mark.skipif(not _HAS_DB, reason="database not available")
def test_workspace_state_round_trip(tmp_path):
    orig = database.DATABASE_PATH
    database.DATABASE_PATH = str(tmp_path / "exh.db")
    database.initialize_database()
    try:
        arrangement = {"components": [{"id": "v1", "type": "vibration"}]}
        database.save_explorer_history_entry(
            entry_type="workspace_state",
            active_user="op1",
            arrangement_json=json.dumps(arrangement),
        )
        rows = database.get_explorer_history(limit=10)
        assert len(rows) >= 1
        stored = json.loads(rows[0]["arrangement_json"])
        assert stored["components"][0]["id"] == "v1"
    finally:
        database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_DB, reason="database not available")
def test_classification_round_trip(tmp_path):
    orig = database.DATABASE_PATH
    database.DATABASE_PATH = str(tmp_path / "exh2.db")
    database.initialize_database()
    try:
        database.save_explorer_history_entry(
            entry_type="classification",
            active_user="op1",
            arrangement_json="{}",
            classification_label="Normal",
            confidence=0.95,
            model_version="explorer-v1.0",
        )
        rows = database.get_explorer_history(limit=10)
        assert rows[0]["classification_label"] == "Normal"
        assert rows[0]["confidence"] == pytest.approx(0.95)
    finally:
        database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_DB, reason="database not available")
def test_entries_in_reverse_chronological_order(tmp_path):
    orig = database.DATABASE_PATH
    database.DATABASE_PATH = str(tmp_path / "exh3.db")
    database.initialize_database()
    try:
        for i in range(3):
            database.save_explorer_history_entry(
                entry_type="workspace_state",
                active_user="op1",
                arrangement_json=json.dumps({"i": i}),
            )
        rows = database.get_explorer_history(limit=10)
        ids = [r["id"] for r in rows]
        assert ids == sorted(ids, reverse=True), "Not in reverse order"
    finally:
        database.DATABASE_PATH = orig


@pytest.mark.skipif(not _HAS_DB, reason="database not available")
def test_get_entry_by_id(tmp_path):
    orig = database.DATABASE_PATH
    database.DATABASE_PATH = str(tmp_path / "exh4.db")
    database.initialize_database()
    try:
        database.save_explorer_history_entry(
            entry_type="classification",
            active_user="op1",
            arrangement_json='{"x":1}',
            classification_label="Fault",
            confidence=0.8,
        )
        rows = database.get_explorer_history(limit=1)
        entry_id = rows[0]["id"]
        entry = database.get_explorer_history_entry(entry_id)
        assert entry is not None
        assert entry["id"] == entry_id
    finally:
        database.DATABASE_PATH = orig
