#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
app_user="${SUDO_USER:-$(id -un)}"
app_group="$(id -gn "$app_user")"
template="$project_dir/deploy/campus-dashboard.service.template"
target="/etc/systemd/system/campus-dashboard.service"

if [[ ! -x "$project_dir/.venv/bin/gunicorn" ]]; then
    "$project_dir/.venv/bin/pip" install -r "$project_dir/requirements.txt"
fi

sed \
    -e "s|__APP_USER__|$app_user|g" \
    -e "s|__APP_GROUP__|$app_group|g" \
    -e "s|__PROJECT_DIR__|$project_dir|g" \
    "$template" | sudo tee "$target" >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable --now campus-dashboard.service
sudo systemctl restart campus-dashboard.service
sudo systemctl --no-pager --full status campus-dashboard.service
