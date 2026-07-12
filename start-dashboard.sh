#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
VENV_DIR=".venv"

# 自动检查并激活虚拟环境
if [ -f "$VENV_DIR/bin/activate" ]; then
  source "$VENV_DIR/bin/activate"
else
  echo "[错误] 虚拟环境未创建，请先运行 ./install-deps.sh"
  exit 1
fi

python start-dashboard.py
