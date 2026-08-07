import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.routers import desktop


class DesktopUpdateAssetTests(unittest.TestCase):
    def test_accepts_versioned_installer_and_blockmap_only(self):
        self.assertTrue(desktop._is_update_asset_name("CampusBoard-1.2.3.exe"))
        self.assertTrue(desktop._is_update_asset_name("CampusBoard-1.2.3.exe.blockmap"))
        self.assertFalse(desktop._is_update_asset_name("latest.yml"))
        self.assertFalse(desktop._is_update_asset_name("../CampusBoard-1.2.3.exe.blockmap"))
        self.assertFalse(desktop._is_update_asset_name("CampusBoard-1.2.3.blockmap"))

    def test_serves_blockmap_and_marks_installer_as_range_capable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            release_dir = Path(temp_dir)
            installer = release_dir / "CampusBoard-1.2.3.exe"
            blockmap = release_dir / "CampusBoard-1.2.3.exe.blockmap"
            installer.write_bytes(bytes(range(100)))
            blockmap.write_bytes(b"blockmap-data")

            with patch.object(desktop, "LOCAL_RELEASE_DIR", release_dir):
                installer_response = desktop.windows_update_file(installer.name)
                blockmap_response = desktop.windows_update_file(blockmap.name)
                blockmap_head = desktop.windows_update_file_head(blockmap.name)

            self.assertEqual(Path(installer_response.path), installer)
            self.assertEqual(installer_response.headers["accept-ranges"], "bytes")
            self.assertEqual(Path(blockmap_response.path), blockmap)
            self.assertEqual(blockmap_response.media_type, "application/octet-stream")
            self.assertEqual(blockmap_response.headers["accept-ranges"], "bytes")
            self.assertEqual(blockmap_head.headers["content-length"], str(len(b"blockmap-data")))


if __name__ == "__main__":
    unittest.main()
