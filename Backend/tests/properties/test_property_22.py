"""
Property 22: Explorer history retention and eviction
Validates: Requirements 6.5, 6.6

Assert that after inserting >500 entries, exactly the 500 most recent
remain, in recency order.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

try:
    import database
    _HAS_DATABASE = True
except ImportError:
    _HAS_DATABASE = False


def _init_temp_db(tmp_dir, name="test.db"):
    """Patch database.DATABASE_PATH to a fresh temp file and initialise the schema."""
    db_path = Path(tmp_dir) / name
    original = database.DATABASE_PATH
    database.DATABASE_PATH = db_path
    database.initialize_database()
    return original


def _restore_db(original):
    database.DATABASE_PATH = original


@pytest.mark.skipif(not _HAS_DATABASE, reason="database module not available")
def test_explorer_history_eviction_at_501():
    """Inserting 501 entries leaves exactly 500, the 500 most recent."""
    with tempfile.TemporaryDirectory() as tmp:
        orig = _init_temp_db(tmp, "eviction_test.db")
        try:
            for i in range(501):
                database.save_explorer_history_entry(
                    entry_type="workspace_state",
                    active_user=f"user_{i}",
                    arrangement_json=f'[{{"id": {i}}}]',
                )

            entries = database.get_explorer_history(limit=1000)
            assert len(entries) == 500, \
                f"Expected exactly 500 entries after eviction, got {len(entries)}"

            # Oldest entry (user_0) should be evicted; user_500 must remain
            users = [e.get("active_user", "") for e in entries]
            assert "user_0" not in users, \
                "The oldest entry (user_0) should have been evicted"
            assert "user_500" in users, \
                "The most recent entry (user_500) must be retained"
        finally:
            _restore_db(orig)


@pytest.mark.skipif(not _HAS_DATABASE, reason="database module not available")
def test_explorer_history_under_500_unaffected():
    """Inserting ≤500 entries leaves all entries intact."""
    with tempfile.TemporaryDirectory() as tmp:
        orig = _init_temp_db(tmp, "under500_test.db")
        try:
            for i in range(50):
                database.save_explorer_history_entry(
                    entry_type="workspace_state",
                    active_user=f"user_{i}",
                    arrangement_json="[]",
                )

            entries = database.get_explorer_history(limit=1000)
            assert len(entries) == 50, \
                f"Expected 50 entries (no eviction below 500), got {len(entries)}"
        finally:
            _restore_db(orig)


@pytest.mark.skipif(not _HAS_DATABASE, reason="database module not available")
def test_explorer_history_reverse_chronological():
    """get_explorer_history returns entries in reverse-chronological order."""
    with tempfile.TemporaryDirectory() as tmp:
        orig = _init_temp_db(tmp, "order_test.db")
        try:
            for i in range(5):
                database.save_explorer_history_entry(
                    entry_type="workspace_state",
                    active_user=f"user_{i}",
                    arrangement_json=f"[{i}]",
                )

            entries = database.get_explorer_history(limit=10)
            assert len(entries) >= 2

            # IDs should be descending (most recent first)
            ids = [e["id"] for e in entries]
            assert ids == sorted(ids, reverse=True), \
                "Entries must be in reverse-chronological (descending ID) order"
        finally:
            _restore_db(orig)
