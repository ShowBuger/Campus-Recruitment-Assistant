#!/bin/bash
cd /root/Campus-Recruitment-Assistant
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