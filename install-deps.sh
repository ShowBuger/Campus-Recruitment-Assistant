#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
VENV_DIR=".venv"

echo
echo "========================================"
echo "  校招信息看板 v0.3 - 一键安装依赖"
echo "========================================"
echo

# 检查 Python
if ! command -v python3 &>/dev/null; then
  echo "[错误] 没有找到 python3。请先安装 Python 3.11+。"
  exit 1
fi

echo "[1/5] 检查 Python 版本..."
python3 --version

echo
echo "[2/5] 创建 Python 虚拟环境..."
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
  echo "[完成] 虚拟环境已创建: $VENV_DIR"
else
  echo "[跳过] 虚拟环境已存在: $VENV_DIR"
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"

echo
echo "[3/5] 升级 pip 并安装依赖..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo
echo "[4/5] 验证全部运行依赖..."
python -c "import fastapi, uvicorn, requests, dotenv, multipart, docx, pypdf, markdown, bleach"
echo "[完成] 全部运行依赖可正常导入。"

echo
echo "[5/5] 验证内置简历分析 Skill..."
if [ ! -f "app/prompts/interview_analysis.md" ]; then
  echo "[错误] 缺少 app/prompts/interview_analysis.md"
  echo "请重新克隆或下载完整项目后再安装。"
  exit 1
fi
echo "[完成] 简历分析 Skill 已随项目安装。"

echo
echo "========================================"
echo "  依赖安装完成！"
echo "========================================"
echo "下一步：运行 ./start-dashboard.sh 启动看板。"
echo "第一次打开网页时，会弹窗引导你填写飞书配置。"
echo
