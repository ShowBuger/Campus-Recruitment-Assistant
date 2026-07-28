#!/bin/bash
cd /opt/campus-recruitment-assistant
gunicorn app.main:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  -b 127.0.0.1:8765 \
  --timeout 180 \
  --keep-alive 30 \
  --access-logfile data/gunicorn-access.log \
  --error-logfile data/gunicorn-error.log