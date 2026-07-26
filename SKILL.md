# 校招信息看板 — 项目管理

## 常用运维命令

### 后端服务

```bash
# 启动后端 API（gunicorn + uvicorn，端口 8765）
bash /opt/campus-recruitment-assistant/start_api.sh

# 停止后端
pkill -f "gunicorn app.main:app"

# 重启后端
pkill -f "gunicorn app.main:app" && sleep 1 && bash /opt/campus-recruitment-assistant/start_api.sh

# 查看后端状态
pgrep -f "gunicorn app.main:app" && echo "✅ 运行中" || echo "❌ 未运行"

# 查看后端日志
tail -f /opt/campus-recruitment-assistant/data/gunicorn-error.log
tail -f /opt/campus-recruitment-assistant/data/gunicorn-access.log
```

### 前端

```bash
# 开发模式（Vite 热更新）
cd /opt/campus-recruitment-assistant/frontend && npx vite --host 0.0.0.0 --port 5173

# 构建生产版本
cd /opt/campus-recruitment-assistant/frontend && npm run build

# 构建并复制到 nginx 静态目录
cd /opt/campus-recruitment-assistant/frontend && npm run build && cp -r dist/* ../static/dist/
```

### Nginx

```bash
# 检查配置并重载
nginx -t && nginx -s reload

# 查看 nginx 状态
systemctl status nginx

# 重启 nginx
systemctl restart nginx
```

### 一键操作

```bash
# 完整启动（后端 + nginx 重载）
bash /opt/campus-recruitment-assistant/start_api.sh && nginx -s reload

# 完整停止
pkill -f "gunicorn app.main:app"

# 一键部署（首次或更新后）
bash /opt/campus-recruitment-assistant/setup.sh
```

### 数据库

```bash
# 查看数据库
sqlite3 /opt/campus-recruitment-assistant/data/app.db

# 备份数据库
cp /opt/campus-recruitment-assistant/data/app.db /opt/campus-recruitment-assistant/data/app.db.bak.$(date +%Y%m%d_%H%M%S)
```

---

## 项目专有 Skill

位于 `skills/` 目录下：

- `skills/company-job-enrichment/` — AI 补全公司类型、方向、岗位 JD
- `skills/recruitment-email-classifier/` — 邮件识别与进展分类
- `skills/job-recommendation/` — 校招岗位智能推荐（S/A/B/C 评分）
