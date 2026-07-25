#!/bin/bash
cd /root/Campus-Recruitment-Assistant
# 同步静态文件到 nginx 目录（/root 权限限制，nginx 无法直接读取）
mkdir -p /var/www/campus-dashboard
cp -r static/dist /var/www/campus-dashboard/dist
gunicorn app.main:app \
  -w 2 \
  -k uvicorn.workers.UvicornWorker \
  -b 127.0.0.1:8765 \
  --timeout 120 \
  --keep-alive 30 \
  --max-requests 1000 \
  --max-requests-jitter 100 \
  --access-logfile data/gunicorn-access.log \
  --error-logfile data/gunicorn-error.log