import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import desktop_releases
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


class DesktopReleaseRetentionTests(unittest.TestCase):
    def test_keeps_latest_three_versions_and_their_blockmaps(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            release_dir = Path(temp_dir)
            for version in ("1.0.8", "1.0.9", "1.0.10", "1.0.11"):
                (release_dir / f"CampusBoard-{version}.exe").write_bytes(b"installer")
                (release_dir / f"CampusBoard-{version}.exe.blockmap").write_bytes(b"blockmap")
            (release_dir / "latest.yml").write_text(
                "version: 1.0.11\npath: CampusBoard-1.0.11.exe\n",
                encoding="utf-8",
            )

            deleted = desktop_releases.cleanup_old_releases(release_dir)

            self.assertEqual(
                deleted,
                ["CampusBoard-1.0.8.exe", "CampusBoard-1.0.8.exe.blockmap"],
            )
            for version in ("1.0.9", "1.0.10", "1.0.11"):
                self.assertTrue((release_dir / f"CampusBoard-{version}.exe").exists())
                self.assertTrue((release_dir / f"CampusBoard-{version}.exe.blockmap").exists())

    def test_protects_metadata_version_and_unrelated_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            release_dir = Path(temp_dir)
            for version in ("1.0.1", "1.0.2", "1.0.3"):
                (release_dir / f"CampusBoard-{version}.exe").write_bytes(b"installer")
            legacy = release_dir / "Campus-Recruitment-Assistant-Setup.exe"
            notes = release_dir / "release-notes.txt"
            legacy.write_bytes(b"legacy")
            notes.write_text("keep", encoding="utf-8")
            (release_dir / "latest.yml").write_text(
                "version: 1.0.1\npath: CampusBoard-1.0.1.exe\n",
                encoding="utf-8",
            )

            deleted = desktop_releases.cleanup_old_releases(
                release_dir, keep_versions=1,
            )

            self.assertEqual(deleted, ["CampusBoard-1.0.2.exe"])
            self.assertTrue((release_dir / "CampusBoard-1.0.1.exe").exists())
            self.assertTrue((release_dir / "CampusBoard-1.0.3.exe").exists())
            self.assertTrue(legacy.exists())
            self.assertTrue(notes.exists())


if __name__ == "__main__":
    unittest.main()
