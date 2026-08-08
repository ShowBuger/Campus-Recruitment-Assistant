"""Retention helpers for locally hosted desktop release assets."""
from __future__ import annotations

import re
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
RELEASE_DIR = PROJECT_DIR / "data" / "desktop-releases"
RELEASE_VERSIONS_TO_KEEP = 3
_ASSET_RE = re.compile(
    r"^CampusBoard-(?P<version>\d+\.\d+\.\d+)\.exe(?:\.blockmap)?$"
)


def _version_key(version: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in version.split("."))


def _metadata_version(release_dir: Path) -> str | None:
    metadata = release_dir / "latest.yml"
    if not metadata.is_file():
        return None
    try:
        for line in metadata.read_text(encoding="utf-8").splitlines():
            if not line.startswith("path:"):
                continue
            name = line.split(":", 1)[1].strip().strip("'\"")
            match = _ASSET_RE.fullmatch(name)
            return match.group("version") if match else None
    except OSError:
        return None
    return None


def cleanup_old_releases(
    release_dir: Path = RELEASE_DIR,
    *,
    keep_versions: int = RELEASE_VERSIONS_TO_KEEP,
) -> list[str]:
    """Delete old versioned installers and blockmaps, returning deleted names.

    Only canonical ``CampusBoard-x.y.z.exe[.blockmap]`` files are considered.
    Metadata, the legacy installer, unrelated files, and the version referenced
    by ``latest.yml`` are always left untouched.
    """
    if keep_versions < 1:
        raise ValueError("keep_versions must be at least 1")
    release_dir = Path(release_dir)
    if not release_dir.is_dir():
        return []

    assets_by_version: dict[str, list[Path]] = {}
    for path in release_dir.iterdir():
        if path.is_symlink() or not path.is_file():
            continue
        match = _ASSET_RE.fullmatch(path.name)
        if match:
            assets_by_version.setdefault(match.group("version"), []).append(path)

    newest = sorted(assets_by_version, key=_version_key, reverse=True)[:keep_versions]
    protected = set(newest)
    metadata_version = _metadata_version(release_dir)
    if metadata_version:
        protected.add(metadata_version)

    deleted: list[str] = []
    for version, paths in assets_by_version.items():
        if version in protected:
            continue
        for path in paths:
            try:
                path.unlink()
                deleted.append(path.name)
            except FileNotFoundError:
                continue
    return sorted(deleted)
