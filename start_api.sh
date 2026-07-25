#!/bin/bash
cd /root/Campus-Recruitment-Assistant
# 同步静态资源到 nginx 目录
cp -r static/* /var/www/campus-dashboard/
gunicorn app.main:app \
  -w 2 \
  -k uvicorn.workers.UvicornWorker \
  -b 127.0.0.1:8765 \
  --timeout 120 \
  --keep-alive 30 \
  --access-logfile data/gunicorn-access.log \
  --error-logfile data/gunicorn-error.log