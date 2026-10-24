#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${RED}[!]${NC} $1"; }
info() { echo -e "${CYAN}[*]${NC} $1"; }

echo
echo "========================================"
echo "  校招信息看板 — 一键部署"
echo "========================================"
echo

# ── 0. 权限检查 ──
if [ "$(id -u)" -ne 0 ]; then
  warn "需要 root 权限运行此脚本"
  exit 1
fi

# ── 1. 系统依赖 ──
info "安装系统包 (nginx, python3, nodejs)..."
if command -v apt &>/dev/null; then
  apt update -qq
  apt install -y -qq nginx python3 python3-pip python3-venv nodejs npm 2>/dev/null
elif command -v yum &>/dev/null; then
  yum install -y nginx python3 python3-pip nodejs npm 2>/dev/null
else
  warn "未识别的包管理器，请手动安装: nginx python3 nodejs npm"
fi

# ── 2. Python 虚拟环境 ──
if [ ! -f ".venv/bin/activate" ]; then
  info "创建 Python 虚拟环境..."
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
log "Python 依赖已安装"

# ── 3. 前端构建 ──
if [ -f "frontend/package.json" ]; then
  info "构建前端..."
  cd frontend
  npm install --silent 2>/dev/null
  npm run build 2>/dev/null
  cd ..
  log "前端构建完成"
else
  warn "未找到 frontend/package.json，跳过前端构建"
fi

# ── 4. 文件权限 ──
# nginx 需要读取项目 static/ 目录
info "设置静态文件权限..."
chmod o+rx /opt/campus-recruitment-assistant
log "项目目录权限已设置"

# ── 5. JWT 密钥 ──
if [ ! -f ".env" ]; then
  python3 -c "
import secrets, os
secret = secrets.token_urlsafe(32)
with open('.env', 'w') as f:
    f.write(f'JWT_SECRET={secret}\n')
"
  log "已生成 .env (JWT_SECRET)"
else
  log ".env 已存在，跳过"
fi

# ── 6. 数据库初始化 ──
info "初始化数据库..."
python3 -c "
import sqlite3, os, bcrypt
os.chdir('$(pwd)')
os.makedirs('data', exist_ok=True)
conn = sqlite3.connect('data/app.db')
conn.execute(\"PRAGMA journal_mode=WAL\")
# 首次启动时 FastAPI 会自动建表，这里确保 data 目录存在
conn.close()
"
log "数据库目录已就绪"

# ── 7. Nginx 配置 ──
if [ -f "deploy/nginx-campus-dashboard.conf" ]; then
  info "部署 nginx 配置..."
  cp deploy/nginx-campus-dashboard.conf /etc/nginx/conf.d/campus-dashboard.conf
  # 替换占位域名（如有）
  DOMAIN="${1:-localhost}"
  if [ "$DOMAIN" != "localhost" ]; then
    sed -i "s/toudimianban\.cloud/$DOMAIN/g" /etc/nginx/conf.d/campus-dashboard.conf
  fi
  nginx -t 2>/dev/null && nginx -s reload 2>/dev/null || warn "nginx 配置测试失败，请手动检查"
  log "nginx 配置已部署"
else
  warn "未找到 deploy/nginx-campus-dashboard.conf"
fi

# ── 8. 启动服务 ──
info "启动后端服务..."
pkill -f "gunicorn app.main:app" 2>/dev/null || true
sleep 1
nohup bash start_api.sh > /tmp/gunicorn.log 2>&1 &
sleep 3
if pgrep -f "gunicorn app.main:app" > /dev/null; then
  log "后端已启动 (端口 8765)"
else
  warn "后端启动失败，查看日志: cat /tmp/gunicorn.log"
fi

echo
echo "========================================"
echo "  部署完成！"
echo "========================================"
echo
echo "  访问地址: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo '服务器IP')"
echo "  首次使用: 注册账号，管理员邀请码或手动创建 root 账号"
echo
echo "  SSL 配置 (推荐):"
echo "    certbot --nginx -d your-domain.com"
echo
echo "  服务管理:"
echo "    启动: bash start_api.sh"
echo "    停止: pkill -f 'gunicorn app.main:app'"
echo "    日志: tail -f data/logs/system.jsonl"
echo
