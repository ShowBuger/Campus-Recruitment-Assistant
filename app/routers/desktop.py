"""Public Windows desktop download and auto-update endpoints."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

router = APIRouter(prefix="/api/desktop", tags=["desktop"])

PROJECT_DIR = Path(__file__).resolve().parents[2]
LOCAL_RELEASE_DIR = PROJECT_DIR / "data" / "desktop-releases"
LEGACY_INSTALLER_NAME = "Campus-Recruitment-Assistant-Setup.exe"


def _is_installer_name(name: str) -> bool:
    return (
        Path(name).name == name
        and name.startswith("CampusBoard-")
        and name.endswith(".exe")
        and len(name) > len("CampusBoard-.exe")
    )


def _is_blockmap_name(name: str) -> bool:
    return name.endswith(".exe.blockmap") and _is_installer_name(name.removesuffix(".blockmap"))


def _is_update_asset_name(name: str) -> bool:
    return _is_installer_name(name) or _is_blockmap_name(name)


def _local_installer() -> Path | None:
    metadata = LOCAL_RELEASE_DIR / "latest.yml"
    if metadata.is_file():
        try:
            for line in metadata.read_text(encoding="utf-8").splitlines():
                if not line.startswith("path:"):
                    continue
                name = line.split(":", 1)[1].strip().strip("'\"")
                if Path(name).name != name or not _is_installer_name(name):
                    return None
                installer = LOCAL_RELEASE_DIR / name
                return installer if installer.is_file() else None
        except OSError:
            return None
        return None

    candidates = list(LOCAL_RELEASE_DIR.glob("CampusBoard-*.exe"))
    legacy = LOCAL_RELEASE_DIR / LEGACY_INSTALLER_NAME
    if legacy.is_file():
        candidates.append(legacy)
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


@router.get("/download/windows")
def download_windows_desktop():
    local_installer = _local_installer()
    if local_installer:
        return FileResponse(
            local_installer,
            media_type="application/vnd.microsoft.portable-executable",
            filename=local_installer.name,
            headers={"Cache-Control": "no-cache"},
        )
    raise HTTPException(status_code=404, detail="Windows 桌面端安装包正在准备中")


@router.get("/updates/windows/latest.yml")
def windows_update_metadata():
    metadata = LOCAL_RELEASE_DIR / "latest.yml"
    if not metadata.is_file():
        raise HTTPException(status_code=404, detail="暂时没有可用更新")
    return FileResponse(
        metadata,
        media_type="application/yaml",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@router.get("/updates/windows/{filename}")
def windows_update_file(filename: str):
    if not _is_update_asset_name(filename):
        raise HTTPException(status_code=404, detail="更新文件不存在")
    asset = LOCAL_RELEASE_DIR / filename
    if not asset.is_file():
        raise HTTPException(status_code=404, detail="更新文件不存在")
    return FileResponse(
        asset,
        media_type=(
            "application/octet-stream"
            if _is_blockmap_name(filename)
            else "application/vnd.microsoft.portable-executable"
        ),
        filename=asset.name,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.head("/updates/windows/{filename}", include_in_schema=False)
def windows_update_file_head(filename: str):
    if not _is_update_asset_name(filename):
        raise HTTPException(status_code=404, detail="更新文件不存在")
    asset = LOCAL_RELEASE_DIR / filename
    if not asset.is_file():
        raise HTTPException(status_code=404, detail="更新文件不存在")
    return Response(
        headers={
            "Content-Length": str(asset.stat().st_size),
            "Content-Type": (
                "application/octet-stream"
                if _is_blockmap_name(filename)
                else "application/vnd.microsoft.portable-executable"
            ),
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'attachment; filename="{asset.name}"',
            "Cache-Control": "public, max-age=31536000, immutable",
        },
    )


@router.get("/release")
def desktop_release_info():
    return {
        "platform": "windows",
        "architecture": "x64",
        "download_url": "/api/desktop/download/windows",
        "available": _local_installer() is not None,
    }
