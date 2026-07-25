# 校招信息看板

校招投递管理工具，支持多用户、多 AI 提供商、邮件跟踪，前后端分离部署。

**当前版本：v0.6**

## 功能

- 多用户注册/登录，每人独立总表、简历、日程、AI 配置
- 投递看板：拖拽卡片更新进展，KPI 统计、筛选、停留时间
- 投递记录：新增/编辑/删除，日历事件、进展追踪
- 总表信息：个人&共享双标签，搜索、排序、导入导出 Excel
- 秋招日历：月视图，投递/机考/面试/保温/结果/截止事件，自定义日程
- 站内聊天：文字/图片/岗位转发，双人实时轮询
- AI 分析：简历+岗位匹配、面试训练、简历优化，支持 DeepSeek/OpenAI/Claude/Kimi
- AI 补全：一键补全公司类型、方向、岗位 JD 等字段
- 邮件跟踪：IMAP 读取招聘邮件，AI 识别进展自动更新
- 浏览器扩展：自动填充投递表单
- 像素风主题 / 经典主题切换

## 快速部署（Linux 服务器）

```bash
git clone https://github.com/ShowBuger/Campus-Recruitment-Assistant.git
cd Campus-Recruitment-Assistant
chmod +x setup.sh
sudo bash setup.sh your-domain.com
```

`setup.sh` 会自动完成：系统依赖 → Python 虚拟环境 → 前端构建 → nginx 配置 → 启动服务。
不传域名参数时默认监听 `localhost`。

## 手动安装

### 环境要求

- Python 3.11+、Node.js 18+、nginx
- 系统包：`python3-venv`、`python3-pip`

### 步骤

```bash
# 1. 后端依赖
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. 前端构建
cd frontend && npm install && npm run build && cd ..

# 3. 静态文件
mkdir -p /var/www/campus-dashboard
cp -r static/dist /var/www/campus-dashboard/dist

# 4. JWT 密钥（首次自动生成）
echo "JWT_SECRET=$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')" > .env

# 5. nginx（SSL 域名）
cp deploy/nginx-campus-dashboard.conf /etc/nginx/conf.d/campus-dashboard.conf
# 编辑配置中的域名和 SSL 证书路径
nginx -t && nginx -s reload

# 6. 启动
bash start_api.sh
```

访问 `https://your-domain.com`，首次使用注册账号。

## 配置

### AI 提供商

在右上角 AI 配置中填写 API Key，支持：

| 提供商 | 默认模型 |
|--------|---------|
| DeepSeek | deepseek-v4-flash |
| OpenAI | gpt-5.4-mini |
| Claude | claude-sonnet-5 |
| Kimi | kimi-k3 |

### 邮件跟踪

右上角进度跟踪配置：填写邮箱+客户端授权码，自动判断 IMAP 服务器和端口。支持大模型识别或本地关键词匹配。

### SSL 证书

```bash
certbot --nginx -d your-domain.com
```

## 服务管理

```bash
bash start_api.sh          # 启动
pkill -f "gunicorn app.main:app"  # 停止
tail -f data/logs/system.jsonl    # 日志
```

## 本地数据

- `data/app.db` — SQLite 数据库（用户、配置、记录、聊天、通知）
- `data/users/` — 简历文件、分析历史
- `.env` — JWT 密钥（不提交到 Git）
- 备份：持久化 `data/` 目录和 `.env` 文件

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | FastAPI / Gunicorn / Uvicorn |
| 数据库 | SQLite（WAL 模式） |
| 前端 | Vue 3 / Vite |
| 样式 | 原生 CSS + Pixelium 像素风主题 |
| AI | DeepSeek / OpenAI / Anthropic / Kimi |
| 部署 | nginx 反向代理 + Let's Encrypt SSL |

## 许可

MIT License
