import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from app import database


class UserStatisticsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "statistics.db"
        self.db_patch = patch.object(database, "DB_PATH", self.db_path)
        self.db_patch.start()
        database._thread_local = database.threading.local()
        database._tables_initialized = False
        self.db = database.get_db()

    def tearDown(self):
        connection = getattr(database._thread_local, "conn", None)
        if connection:
            connection.close()
        database._thread_local = database.threading.local()
        database._tables_initialized = False
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_statistics_include_activity_signups_and_recent_users(self):
        today = date.today()
        self.db.executemany(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, 'hash', ?)",
            [
                ("active-user", f"{today.isoformat()} 01:00:00"),
                ("older-user", f"{(today - timedelta(days=20)).isoformat()} 01:00:00"),
            ],
        )
        self.db.execute(
            "UPDATE users SET last_seen_at = datetime('now') WHERE username = 'active-user'"
        )
        active_id = self.db.execute(
            "SELECT id FROM users WHERE username = 'active-user'"
        ).fetchone()["id"]
        self.db.executemany(
            "INSERT INTO user_daily_activity (user_id, activity_date) VALUES (?, ?)",
            [(active_id, today.isoformat()), (active_id, (today - timedelta(days=1)).isoformat())],
        )
        self.db.commit()

        result = database.get_user_statistics(7)

        self.assertEqual(result["dau"], 1)
        self.assertEqual(result["wau"], 1)
        self.assertEqual(result["mau"], 1)
        self.assertEqual(result["new_users"], 1)
        self.assertEqual(result["total_users"], 2)
        self.assertEqual(result["active_rate"], 50.0)
        self.assertEqual(len(result["series"]), 7)
        self.assertEqual(result["recent_users"][0]["username"], "active-user")
        self.assertEqual(result["recent_users"][0]["active_days"], 2)

    def test_empty_statistics_are_safe(self):
        result = database.get_user_statistics(30)

        self.assertEqual(result["dau"], 0)
        self.assertEqual(result["active_rate"], 0)
        self.assertEqual(len(result["series"]), 30)
        self.assertEqual(result["recent_users"], [])

    def test_ban_invalidates_tokens_and_can_be_lifted_early(self):
        self.db.execute(
            "INSERT INTO users (username, password_hash) VALUES ('member', 'hash')"
        )
        self.db.commit()
        user = database.get_user_by_username("member")

        banned = database.ban_user(user["id"], 24, "违反使用规范")

        self.assertTrue(database.is_user_banned(user["id"]))
        self.assertEqual(banned["ban_reason"], "违反使用规范")
        self.assertEqual(database.get_user_by_id(user["id"])["token_version"], 1)

        database.unban_user(user["id"])

        self.assertFalse(database.is_user_banned(user["id"]))
        self.assertIsNone(database.get_user_by_id(user["id"])["banned_until"])

    def test_root_account_cannot_be_banned(self):
        self.db.execute(
            "INSERT INTO users (username, password_hash) VALUES ('root', 'hash')"
        )
        self.db.commit()
        root = database.get_user_by_username("root")

        with self.assertRaisesRegex(ValueError, "root"):
            database.ban_user(root["id"], 24)


if __name__ == "__main__":
    unittest.main()
