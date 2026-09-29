import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from app.routers import dashboard


class SyncRecoveryTests(unittest.TestCase):
    def test_recovers_sync_owned_by_dead_process(self):
        progress = {
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "owner_pid": 12345,
            "finished": False,
            "phase": "scanning",
        }
        with (
            patch.object(dashboard, "_active_sync_get", return_value="stuck-sync"),
            patch.object(dashboard, "_sync_progress_get", return_value=progress),
            patch.object(dashboard, "_process_is_alive", return_value=False),
            patch.object(dashboard, "_sync_progress_set") as save_progress,
            patch.object(dashboard, "_active_sync_set") as save_active,
            patch.object(dashboard.bus, "log"),
        ):
            active = dashboard._recover_orphaned_active_sync()

        self.assertIsNone(active)
        self.assertTrue(progress["finished"])
        self.assertTrue(progress["failed"])
        save_progress.assert_called_once_with("stuck-sync", progress)
        save_active.assert_called_once_with(None)

    def test_preserves_live_recent_sync(self):
        progress = {
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "owner_pid": 12345,
            "finished": False,
        }
        with (
            patch.object(dashboard, "_active_sync_get", return_value="live-sync"),
            patch.object(dashboard, "_sync_progress_get", return_value=progress),
            patch.object(dashboard, "_process_is_alive", return_value=True),
            patch.object(dashboard, "_sync_progress_set") as save_progress,
            patch.object(dashboard, "_active_sync_set") as save_active,
        ):
            active = dashboard._recover_orphaned_active_sync()

        self.assertEqual(active, "live-sync")
        save_progress.assert_not_called()
        save_active.assert_not_called()

    def test_recovers_stale_legacy_sync(self):
        progress = {
            "started_at": (datetime.now() - timedelta(hours=3)).isoformat(timespec="seconds"),
            "finished": False,
        }
        with (
            patch.object(dashboard, "_active_sync_get", return_value="legacy-sync"),
            patch.object(dashboard, "_sync_progress_get", return_value=progress),
            patch.object(dashboard, "_sync_progress_set"),
            patch.object(dashboard, "_active_sync_set") as save_active,
            patch.object(dashboard.bus, "log"),
        ):
            active = dashboard._recover_orphaned_active_sync()

        self.assertIsNone(active)
        save_active.assert_called_once_with(None)


if __name__ == "__main__":
    unittest.main()
