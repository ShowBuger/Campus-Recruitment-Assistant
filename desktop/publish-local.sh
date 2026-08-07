#!/usr/bin/env bash
set -euo pipefail

desktop_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
project_dir=$(cd "$desktop_dir/.." && pwd)
release_dir="$project_dir/data/desktop-releases"
version=$(node -p "require('$desktop_dir/package.json').version")
installer_name="CampusBoard-$version.exe"
blockmap_name="$installer_name.blockmap"
installer_source="$desktop_dir/dist-electron/$installer_name"
blockmap_source="$desktop_dir/dist-electron/$blockmap_name"
metadata_source="$desktop_dir/dist-electron/latest.yml"

test -f "$installer_source"
test -f "$blockmap_source"
test -f "$metadata_source"
grep -Fxq "version: $version" "$metadata_source"
grep -Fxq "path: $installer_name" "$metadata_source"
gzip -t "$blockmap_source"
mkdir -p "$release_dir"

if [[ -e "$release_dir/$installer_name" || -e "$release_dir/$blockmap_name" ]]; then
  printf 'Refusing to overwrite immutable release %s. Increase the desktop version first.\n' "$version" >&2
  exit 1
fi

installer_temp=$(mktemp "$release_dir/.${installer_name}.XXXXXX")
blockmap_temp=$(mktemp "$release_dir/.${blockmap_name}.XXXXXX")
metadata_temp=$(mktemp "$release_dir/.latest.yml.XXXXXX")
installer_size=$(stat -c %s "$installer_source")

cleanup() {
  rm -f -- "$installer_temp" "$blockmap_temp" "$metadata_temp"
}
trap cleanup EXIT

install -m 0644 "$installer_source" "$installer_temp"
install -m 0644 "$blockmap_source" "$blockmap_temp"
metadata_size=$(awk '$1 == "size:" { print $2; exit }' "$metadata_source")
if [[ -n "$metadata_size" ]]; then
  if [[ "$metadata_size" != "$installer_size" ]]; then
    printf 'Installer size does not match latest.yml (%s != %s).\n' "$installer_size" "$metadata_size" >&2
    exit 1
  fi
  install -m 0644 "$metadata_source" "$metadata_temp"
else
  awk -v size="$installer_size" '
    { print }
    !added && /^    sha512:/ {
      print "    size: " size
      added = 1
    }
  ' "$metadata_source" > "$metadata_temp"
fi
chmod 0644 "$metadata_temp"
mv -fT "$installer_temp" "$release_dir/$installer_name"
mv -fT "$blockmap_temp" "$release_dir/$blockmap_name"
mv -fT "$metadata_temp" "$release_dir/latest.yml"

trap - EXIT

(
  cd "$project_dir"
  .venv/bin/python - "$version" <<'PY'
import sys

from app import database

version = sys.argv[1]
database.get_db()
database.create_notification(
    title=f"桌面端 v{version} 已发布",
    content=(
        f"Windows 桌面端 v{version} 已发布。"
        "桌面端会自动检查并下载更新，也可以从网页右上角重新下载安装包。"
    ),
    created_by=None,
    request_id=f"desktop-release-{version}",
)
PY
)

printf 'Published %s atomically.\n' "$installer_name"
