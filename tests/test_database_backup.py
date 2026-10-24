import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from app import database_backup


class DatabaseBackupRetentionTests(unittest.TestCase):
    def test_cleanup_keeps_only_backups_from_last_three_days(self):
        now = time.time()
        with tempfile.TemporaryDirectory() as directory:
            backup_dir = Path(directory)
            recent = backup_dir / "auto-recent.db"
            expired = backup_dir / "manual-expired.db"
            unrelated = backup_dir / "notes.txt"
            for path in (recent, expired, unrelated):
                path.write_bytes(b"test")
            os.utime(recent, (now - 2 * 86400, now - 2 * 86400))
            os.utime(expired, (now - 4 * 86400, now - 4 * 86400))
            os.utime(unrelated, (now - 10 * 86400, now - 10 * 86400))

            with patch.object(database_backup, "BACKUP_DIR", backup_dir):
                deleted = database_backup.cleanup_expired_backups(now=now)

            self.assertEqual(deleted, [expired.name])
            self.assertTrue(recent.exists())
            self.assertFalse(expired.exists())
            self.assertTrue(unrelated.exists())


if __name__ == "__main__":
    unittest.main()
