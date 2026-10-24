import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from app import database, local_records


class OfferDetailsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        data_dir = Path(self.temp_dir.name)
        self.patches = [
            patch.object(database, "DATA_DIR", data_dir),
            patch.object(database, "DB_PATH", data_dir / "app.db"),
            patch.object(database, "_tables_initialized", False),
            patch.object(database, "_thread_local", threading.local()),
        ]
        for active_patch in self.patches:
            active_patch.start()
        db = database.get_db()
        db.execute(
            "INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)",
            (1, "offer-user", "hash"),
        )
        db.commit()

    def tearDown(self):
        connection = getattr(database._thread_local, "conn", None)
        if connection:
            connection.close()
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.temp_dir.cleanup()

    def test_structured_offer_details_round_trip(self):
        created = local_records.create_record(1, {
            "公司名称": "星河科技",
            "秋招岗位": "后端开发",
            "Offer详情": {
                "base_annual": 240000,
                "equity_type": "RSU",
                "growth_score": 8,
                "red_flags": "奖金定义需确认",
            },
        })

        record = local_records.get_record(1, created["record_id"])
        details = record["fields"]["Offer详情"]
        self.assertEqual(details["base_annual"], 240000)
        self.assertEqual(details["equity_type"], "RSU")
        self.assertEqual(details["growth_score"], 8)
        self.assertEqual(details["red_flags"], "奖金定义需确认")

    def test_legacy_offer_columns_are_not_created(self):
        columns = {
            row["name"]
            for row in database.get_db().execute("PRAGMA table_info(job_records)")
        }
        self.assertIn("offer_details", columns)
        self.assertTrue({
            "offer_total", "offer_base", "offer_bonus", "offer_deadline"
        }.isdisjoint(columns))


if __name__ == "__main__":
    unittest.main()
