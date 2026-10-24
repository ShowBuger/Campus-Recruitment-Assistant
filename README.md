# 校招信息看板

校招投递全流程管理平台，支持多用户协作、AI 智能分析、邮件自动跟踪和薪资查询。

**当前版本：v1.5.5**

## 核心功能

### 📊 投递管理
- **看板视图**：拖拽卡片更新进展，可视化投递漏斗，实时 KPI 统计
- **投递记录**：完整的增删改查，支持子记录分组、批量操作、智能排序
- **总表信息**：个人与共享数据双视图，支持搜索、筛选、Excel 导入导出
- **日历视图**：月视图展示投递、笔试、面试等关键节点，支持自定义日程

### 🤖 AI 智能助手
- **简历分析**：AI 评估简历质量，生成优化建议
- **岗位匹配**：简历与 JD 智能匹配度分析
- **面试训练**：模拟面试场景，生成面试题和参考答案
- **Offer 对比**：多个 Offer 智能对比分析，辅助决策
- **智能补全**：一键补全公司类型、业务方向、岗位 JD 等字段
- **多模型支持**：DeepSeek、OpenAI、Claude、Kimi 可自由切换

### 💬 协作与沟通
- **站内聊天**：好友系统，支持文字、图片和岗位信息分享
- **通知中心**：好友申请、系统通知统一管理
- **共享总表**：团队成员共享岗位信息，避免重复投递
- **岗位推荐**：基于个人投递历史的智能推荐

### 📧 自动化工具
- **邮件跟踪**：IMAP 自动读取招聘邮件，AI 识别进展并更新记录
- **浏览器扩展**：自动填充投递表单，提高投递效率
- **进度自动更新**：根据填写的时间字段自动更新进展状态

### 💰 薪资查询
- **双数据源**：支持飞书在线表格和 OfferShow 薪资数据
- **飞书授权**：管理员可在界面直接完成飞书授权
- **公共配置**：管理员配置公共 Token，所有用户可查询

### 🎨 用户体验
- **双主题**：像素风主题（Pixelium）/ 经典主题自由切换
- **响应式设计**：支持桌面端和移动端访问
- **多用户系统**：独立的个人数据空间和 AI 配置

### 🔐 管理功能
- **用户管理**：用户权限控制、封禁解封、密码重置
- **数据统计**：活跃用户分析、投递数据趋势
- **通知发布**：全局通知推送
- **数据备份**：定期自动备份，支持一键恢复

## 快速部署

### 一键部署（推荐）

```bash
git clone https://github.com/ShowBuger/Campus-Recruitment-Assistant.git
cd Campus-Recruitment-Assistant
sudo bash setup.sh your-domain.com
```

`setup.sh` 会自动完成所有安装配置工作，不传域名参数时默认监听本地。

### 手动部署

```bash
# 1. 安装依赖
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..

# 2. 生成配置
echo "JWT_SECRET=$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')" > .env

# 3. 配置 nginx（可选）
cp deploy/nginx-campus-dashboard.conf /etc/nginx/conf.d/campus-dashboard.conf
# 编辑配置中的域名，然后重载 nginx

# 4. 启动服务
bash start_api.sh
```

访问配置的域名或 `http://localhost:8000`，首次使用需要注册账号。

## 使用指南

### AI 功能配置

在右上角 **AI 配置** 中填写 API Key：

| 提供商 | 默认模型 | 获取地址 |
|--------|---------|---------|
| DeepSeek | deepseek-v4-flash | [platform.deepseek.com](https://platform.deepseek.com) |
| OpenAI | gpt-5.4-mini | [platform.openai.com](https://platform.openai.com) |
| Claude | claude-sonnet-5 | [console.anthropic.com](https://console.anthropic.com) |
| Kimi | kimi-k3 | [platform.moonshot.cn](https://platform.moonshot.cn) |

配置后即可使用简历分析、岗位匹配、面试训练等 AI 功能。

### 邮件跟踪配置

在右上角 **进度跟踪** 配置：

1. 填写邮箱地址（支持 QQ、163、Gmail 等）
2. 填写客户端授权码（非邮箱密码，需在邮箱设置中开启 IMAP 并生成）
3. 选择识别方式：AI 模型识别（精准）或关键词匹配（快速）

配置后系统会自动读取招聘邮件，识别进展并更新投递记录。

### 薪资查询配置（管理员）

管理员在 **管理界面 → 薪资查询** 配置：

**方式一：飞书薪资表**
1. 点击"开始授权"
2. 扫描二维码或访问授权链接
3. 使用飞书 App 完成授权

**方式二：OfferShow Token**
1. 登录 [offershow.cn](https://www.offershow.cn)
2. 从浏览器开发者工具 → Application → Local Storage 复制 `usertoken`
3. 粘贴到管理界面保存

配置后，所有用户可在薪资查询页面使用这些数据源。

### 好友与聊天

1. 打开右上角 **站内聊天**
2. 在联系人区域输入对方用户名，发送好友申请
3. 对方在 **通知中心** 接受申请
4. 成为好友后可发送文字、图片和岗位信息

### SSL 证书配置

使用 Let's Encrypt 自动获取免费 SSL 证书：

```bash
sudo certbot --nginx -d your-domain.com
```

## 服务管理

```bash
# 启动服务
bash start_api.sh

# 停止服务
pkill -f "gunicorn app.main:app"

# 查看日志
tail -f data/gunicorn-error.log
```

## 数据备份与恢复

### 备份数据

```bash
# 备份整个 data 目录（推荐）
tar -czf backup-$(date +%Y%m%d).tar.gz data/ .env

# 或仅备份数据库
cp data/app.db data/app.db.backup-$(date +%Y%m%d)
```

### 恢复数据

```bash
# 停止服务
pkill -f "gunicorn app.main:app"

# 恢复备份
tar -xzf backup-YYYYMMDD.tar.gz
# 或
cp data/app.db.backup-YYYYMMDD data/app.db

# 重启服务
bash start_api.sh
```

管理界面提供自动备份功能（每 12 小时），最多保留最近 3 天的备份。

## 常见问题

### 启动失败：端口被占用

```bash
# 查找占用 8765 端口的进程
sudo lsof -i :8765
# 杀死进程
kill -9 <PID>
```

### 前端更新后页面未刷新

清除浏览器缓存或强制刷新（Ctrl+Shift+R / Cmd+Shift+R）。

### AI 分析失败

检查：
1. API Key 是否正确配置
2. 账户余额是否充足
3. 网络是否可以访问 API 端点

### 邮件跟踪无法连接

确认：
1. 邮箱已开启 IMAP 服务
2. 使用的是客户端授权码，不是登录密码
3. 防火墙未阻止 IMAP 端口（通常是 993）

## 许可协议

MIT License

## 联系方式

- 项目主页：[GitHub](https://github.com/ShowBuger/Campus-Recruitment-Assistant)
- 问题反馈：[Issues](https://github.com/ShowBuger/Campus-Recruitment-Assistant/issues)
