
"""
INTELLIWATCH - CONSOLIDATED ENGINE TEST SUITE
11 tests using isolated temporary SQLite databases.
"""

import unittest
import tempfile
import sqlite3

from pathlib import Path
from contextlib import closing

from intelliwatch_engine import IntelliWatchEngine


class TestIntelliWatchEngine(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            ignore_cleanup_errors=True
        )

        self.db_path = (
            Path(self.temp_dir.name) / "test_intelliwatch.db"
        )

        self.engine = IntelliWatchEngine(
            database_path=str(self.db_path)
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    # -----------------------------------------
    # Helper: Safely read database values
    # -----------------------------------------

    def get_database_value(self, query):
        with closing(sqlite3.connect(self.db_path)) as conn:
            return conn.execute(query).fetchone()[0]

    # -----------------------------------------
    # Helper: Generate sensor readings
    # -----------------------------------------

    def readings(self, vibration, temperature, current):
        return [
            {
                "sensor_type": "ADXL345",
                "sensor_name": "Vibration Sensor",
                "parameter": "magnitude",
                "value": vibration,
                "unit": "g",
                "quality": "GOOD"
            },
            {
                "sensor_type": "DS18B20",
                "sensor_name": "Temperature Sensor",
                "parameter": "temperature",
                "value": temperature,
                "unit": "C",
                "quality": "GOOD"
            },
            {
                "sensor_type": "ACS712",
                "sensor_name": "Current Sensor",
                "parameter": "current",
                "value": current,
                "unit": "A",
                "quality": "GOOD"
            }
        ]

    # -----------------------------------------
    # Helper: Register known patterns
    # -----------------------------------------

    def register_knowledge(self):
        normal_samples = [
            (0.20, 30.0, 1.50),
            (0.21, 30.5, 1.55),
            (0.22, 31.0, 1.60),
            (0.23, 31.5, 1.65),
            (0.24, 32.0, 1.70)
        ]

        abnormal_samples = [
            (0.80, 70.0, 8.00),
            (0.81, 70.5, 8.05),
            (0.82, 71.0, 8.10),
            (0.83, 71.5, 8.15),
            (0.84, 72.0, 8.20)
        ]

        for sample in normal_samples:
            self.engine.learn_from_verified_pattern(
                self.readings(*sample),
                "normal",
                "test_user"
            )

        for sample in abnormal_samples:
            self.engine.learn_from_verified_pattern(
                self.readings(*sample),
                "abnormal",
                "test_user"
            )

    # -----------------------------------------
    # TEST 1: Normal pattern learning
    # -----------------------------------------

    def test_normal_learning(self):
        self.engine.learn_from_verified_pattern(
            self.readings(0.20, 30.0, 1.50),
            "normal",
            "test_user"
        )

        count = self.get_database_value(
            "SELECT COUNT(*) FROM knowledge_profiles "
            "WHERE label = 'normal'"
        )

        self.assertGreater(count, 0)

    # -----------------------------------------
    # TEST 2: Abnormal pattern learning
    # -----------------------------------------

    def test_abnormal_learning(self):
        self.engine.learn_from_verified_pattern(
            self.readings(0.80, 70.0, 8.00),
            "abnormal",
            "test_user"
        )

        count = self.get_database_value(
            "SELECT COUNT(*) FROM knowledge_profiles "
            "WHERE label = 'abnormal'"
        )

        self.assertGreater(count, 0)

    # -----------------------------------------
    # TEST 3: Individual sensor analysis
    # -----------------------------------------

    def test_sensor_independence(self):
        self.register_knowledge()

        result = self.engine.process_readings(
            self.readings(0.82, 31.0, 1.60)
        )

        statuses = result["sensor_statuses"]

        self.assertIn("vibration", statuses)
        self.assertIn("temperature", statuses)
        self.assertIn("current", statuses)

        self.assertNotEqual(
            statuses["vibration"],
            statuses["temperature"]
        )

    # -----------------------------------------
    # TEST 4: Overall system status
    # -----------------------------------------

    def test_unified_system_status(self):
        self.register_knowledge()

        result = self.engine.process_readings(
            self.readings(0.82, 70.5, 8.05)
        )

        overall = result["overall_system_status"]

        self.assertIsInstance(overall, dict)

        self.assertIn(
            overall["status"],
            [
                "NORMAL",
                "WARNING",
                "CRITICAL",
                "UNDER_OBSERVATION"
            ]
        )

    # -----------------------------------------
    # TEST 5: Similar unknown patterns grouping
    # -----------------------------------------

    def test_unknown_pattern_grouping(self):
        samples = [
            (0.45, 45.0, 3.00),
            (0.46, 45.2, 3.02),
            (0.44, 44.9, 2.98),
            (0.47, 45.1, 3.01),
            (0.45, 45.3, 3.03),
            (0.46, 45.0, 2.99),
            (0.44, 45.2, 3.01)
        ]

        pattern_ids = []

        for sample in samples:
            result = self.engine.process_readings(
                self.readings(*sample)
            )

            pattern_ids.append(
                result["combined_pattern"]["pattern_id"]
            )

        self.assertEqual(len(set(pattern_ids)), 1)

    # -----------------------------------------
    # TEST 6: Different unknown patterns
    # -----------------------------------------

    def test_unknown_pattern_separation(self):
        first = self.engine.process_readings(
            self.readings(0.45, 45.0, 3.00)
        )

        second = self.engine.process_readings(
            self.readings(1.50, 90.0, 15.0)
        )

        first_id = first["combined_pattern"]["pattern_id"]
        second_id = second["combined_pattern"]["pattern_id"]

        self.assertNotEqual(first_id, second_id)

    # -----------------------------------------
    # TEST 7: Invalid sensor data handling
    # -----------------------------------------

    def test_invalid_sensor_data(self):
        invalid_readings = [
            {
                "sensor_type": "ADXL345",
                "sensor_name": "Vibration Sensor",
                "parameter": "magnitude",
                "value": 0.50,
                "unit": "g",
                "quality": "BAD"
            }
        ]

        with self.assertRaises(ValueError):
            self.engine.process_readings(invalid_readings)

    # -----------------------------------------
    # TEST 8: Operating limits
    # -----------------------------------------

    def test_operating_limits(self):
        self.engine.set_operating_limits({
            "vibration": {
                "warning_minimum": 0.30,
                "warning_maximum": 0.60,
                "critical_minimum": 0.70,
                "critical_maximum": 1.00
            }
        })

        result = self.engine.analyse_sensor(
            "vibration",
            0.80
        )

        self.assertIsInstance(result, dict)

        self.assertIn(
            result["status"],
            ["WARNING", "CRITICAL"]
        )

    # -----------------------------------------
    # TEST 9: Database persistence
    # -----------------------------------------

    def test_database_persistence(self):
        self.engine.learn_from_verified_pattern(
            self.readings(0.20, 30.0, 1.50),
            "normal",
            "test_user"
        )

        restarted_engine = IntelliWatchEngine(
            database_path=str(self.db_path)
        )

        count = self.get_database_value(
            "SELECT COUNT(*) FROM knowledge_profiles "
            "WHERE label = 'normal'"
        )

        self.assertGreater(count, 0)

        self.assertGreater(
            restarted_engine.get_knowledge_summary()[
                "combined_normal_profiles"
            ],
            0
        )

    # -----------------------------------------
    # TEST 10: Manual review
    # -----------------------------------------

    def test_manual_review(self):
        result = self.engine.process_readings(
            self.readings(0.45, 45.0, 3.00),
            mode="manual"
        )

        pattern_id = result["combined_pattern"]["pattern_id"]

        review_result = self.engine.add_manual_review_note(
            pattern_id,
            "human_reviewer",
            "Test review note"
        )

        self.assertIsNotNone(review_result)
        self.assertTrue(review_result["success"])

    # -----------------------------------------
    # TEST 11: SQLite integrity
    # -----------------------------------------

    def test_database_integrity(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            result = conn.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]

        self.assertEqual(result, "ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)
