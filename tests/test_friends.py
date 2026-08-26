import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from app import chat_store, database, friend_store


class FriendStoreTests(unittest.TestCase):
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
            [(1, "alice", "hash"), (2, "Bob", "hash"), (3, "carol", "hash")],
        )
        db.commit()

    def tearDown(self):
        connection = getattr(database._thread_local, "conn", None)
        if connection:
            connection.close()
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.temp_dir.cleanup()

    def test_request_by_username_and_accept_creates_mutual_friendship(self):
        request = friend_store.create_request(1, "bob")
        self.assertEqual(request["receiver"]["id"], 2)
        self.assertEqual(friend_store.count_pending_requests(2), 1)
        received = friend_store.list_received_requests(2)
        self.assertEqual(received[0]["sender_username"], "alice")

        result = friend_store.respond_to_request(2, request["id"], True)
        self.assertEqual(result["status"], "accepted")
        self.assertTrue(friend_store.are_friends(1, 2))
        self.assertTrue(friend_store.are_friends(2, 1))
        self.assertEqual([user["username"] for user in chat_store.list_chat_users(1)], ["Bob"])

    def test_reject_does_not_create_friendship(self):
        request = friend_store.create_request(1, "carol")
        friend_store.respond_to_request(3, request["id"], False)
        self.assertFalse(friend_store.are_friends(1, 3))
        self.assertEqual(chat_store.list_chat_users(1), [])

    def test_duplicate_self_and_reverse_requests_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "自己"):
            friend_store.create_request(1, "alice")
        friend_store.create_request(1, "Bob")
        with self.assertRaisesRegex(ValueError, "已发送"):
            friend_store.create_request(1, "Bob")
        with self.assertRaisesRegex(ValueError, "对方已向你"):
            friend_store.create_request(2, "alice")


if __name__ == "__main__":
    unittest.main()
