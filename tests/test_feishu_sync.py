import json
import sqlite3
import unittest
from unittest.mock import patch

from app import database, feishu_sync
from app.routers import dashboard


class FeishuSyncTests(unittest.TestCase):
    def test_token_missing_error_is_actionable_and_does_not_leak_cli_json(self):
        output = json.dumps({
            "ok": False,
            "error": {
                "type": "authentication",
                "subtype": "token_missing",
                "message": "need_user_authorization",
                "user_open_id": "ou_secret",
            },
        })
        message = feishu_sync._cli_error_message(output)
        self.assertIn("重新授权", message)
        self.assertIn("sheets:spreadsheet:read", message)
        self.assertNotIn("ou_secret", message)

    def test_saved_sync_url_can_be_overwritten(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE user_configs ("
            "user_id INTEGER PRIMARY KEY, feishu_sync_url TEXT NOT NULL DEFAULT '')"
        )
        with patch("app.database.get_db", return_value=conn):
            database.save_feishu_sync_url(1, "https://a.feishu.cn/sheets/old")
            database.save_feishu_sync_url(1, "https://a.feishu.cn/sheets/new")
        saved = conn.execute(
            "SELECT feishu_sync_url FROM user_configs WHERE user_id = 1"
        ).fetchone()[0]
        self.assertEqual(saved, "https://a.feishu.cn/sheets/new")

    def test_empty_request_uses_saved_url(self):
        saved_url = "https://example.feishu.cn/sheets/saved"
        with (
            patch(
                "app.routers.dashboard.database.get_user_config",
                return_value={"feishu_sync_url": saved_url},
            ),
            patch("app.routers.dashboard.database.save_feishu_sync_url") as save,
            patch(
                "app.routers.dashboard.feishu_sync.validate_url",
                return_value=saved_url,
            ),
            patch("app.routers.dashboard.feishu_sync.read_table", return_value=[]),
            patch("app.routers.dashboard.feishu_sync.prepare_sync", return_value=([], [], 0)),
            patch("app.routers.dashboard.local_records.list_records", return_value=[]),
            patch("app.routers.dashboard.local_records.get_dashboard_data", return_value={}),
            patch("app.routers.dashboard.state.set_cache"),
        ):
            result = dashboard.sync_feishu_records(
                dashboard.FeishuSyncRequest(),
                user={"user_id": 1, "is_root": True},
            )
        save.assert_called_once_with(1, saved_url)
        self.assertEqual(result["url"], saved_url)


if __name__ == "__main__":
    unittest.main()
