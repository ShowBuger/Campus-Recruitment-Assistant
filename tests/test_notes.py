import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from app import database, local_records, notes_store


class NoteStoreTests(unittest.TestCase):
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
        db.executemany(
            "INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)",
            [(1, "note-user", "hash"), (2, "other-user", "hash")],
        )
        db.commit()

    def tearDown(self):
        connection = getattr(database._thread_local, "conn", None)
        if connection:
            connection.close()
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.temp_dir.cleanup()

    def test_nested_notes_are_user_scoped_and_cascade_on_delete(self):
        root = notes_store.create_note(1, "面试准备")
        child = notes_store.create_note(1, "项目复盘", parent_id=root["id"])

        self.assertEqual(child["parent_id"], root["id"])
        self.assertEqual(len(notes_store.list_notes(1)), 2)
        self.assertEqual(notes_store.list_notes(2), [])
        with self.assertRaisesRegex(ValueError, "父笔记不存在"):
            notes_store.create_note(2, "越权子笔记", parent_id=root["id"])

        self.assertTrue(notes_store.delete_note(1, root["id"]))
        self.assertEqual(notes_store.list_notes(1), [])

    def test_markdown_content_and_application_link_are_persisted(self):
        record = local_records.create_record(1, {
            "公司名称": "星河科技",
            "秋招岗位": "后端开发",
        })
        note = notes_store.create_note(1, "投递复盘", record_id=record["record_id"])
        updated = notes_store.update_note(
            1,
            note["id"],
            "一面复盘",
            "# 一面复盘\n\n## 算法题\n\n记录解题思路。",
            record["record_id"],
        )

        self.assertIn("## 算法题", updated["content"])
        self.assertEqual(updated["record"]["company"], "星河科技")
        with self.assertRaisesRegex(ValueError, "关联的投递记录不存在"):
            notes_store.update_note(2, note["id"], "越权", "", record["record_id"])


if __name__ == "__main__":
    unittest.main()
