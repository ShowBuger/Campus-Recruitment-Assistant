# 校招信息看板

本地运行的校招投递管理工具。职位、投递进度和用户数据保存在本地 SQLite，在浏览器中维护记录、预览简历，并使用 DeepSeek 分析简历与岗位的匹配情况。

**当前版本：v0.5**

## 功能

- 多用户支持：注册/登录，每人拥有独立的本地总表、简历、日程与 AI 配置
- 看板总览：公司数量、投递漏斗、截止时间、方向与公司类型分布
- 投递记录：新增和编辑记录；移出投递时保留主表行并重置投递流程
- 总表信息：浏览、编辑和永久删除本地记录，维护优先级、备注和岗位 JD
- 秋招日历：按月查看投递、机考/笔试、面试、保温、结果和截止事件；点击"新建日程"可直接在日历上为已有记录添加日期，或创建无需绑定公司的自定义本地日程
- 简历预览：上传 PDF/DOCX 到本地 `resume/`，直接在网页中预览
- 简历分析：选择简历和总表岗位，调用 DeepSeek 输出 Markdown 分析报告
- 分析历史：分析结果以 JSON 保存在本地 `analysis_history/`，可随时二次预览
- AI 配置：按用户管理 DeepSeek API Key 和模型
- 亮色/暗色主题

## 环境要求

- Python 3.11 或更高版本
- Windows 10/11 推荐使用 `.bat` 脚本，Linux/macOS 使用 `.sh` 脚本
- 使用 AI 分析时需要能够访问 `api.deepseek.com`

## 快速安装

### Windows

1. 克隆项目：

```powershell
git clone https://github.com/ShowBuger/Campus-Recruitment-Assistant.git
cd Campus-Recruitment-Assistant
```

2. 双击 `install-deps.bat`，脚本会安装 `requirements.txt` 中的全部依赖。
3. 双击 `start-dashboard.bat`。
4. 打开 `http://localhost:8765`，首次使用需注册账号。

### Linux / macOS

1. 克隆项目：

```bash
git clone https://github.com/ShowBuger/Campus-Recruitment-Assistant.git
cd Campus-Recruitment-Assistant
```

2. 给脚本添加执行权限并安装依赖：

```bash
chmod +x install-deps.sh start-dashboard.sh
./install-deps.sh
```

3. 启动看板：

```bash
./start-dashboard.sh
```

4. 打开 `http://localhost:8765`。

`start-dashboard.py` 启动时也会检查全部运行依赖，发现缺失后自动执行：

```powershell
python -m pip install -r requirements.txt
```

简历分析 skill 已内置在 `app/prompts/interview_analysis.md`，随仓库一起安装。安装脚本和启动脚本都会校验该文件，缺失时停止运行并提示重新获取完整项目，不需要额外克隆 `interview-skills` 仓库。

### 命令行（所有平台通用）

```bash
# 安装依赖
python3 -m pip install -r requirements.txt

# 启动看板
python3 start-dashboard.py

# 或直接使用 uvicorn
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

## 配置

职位总表无需外部配置。注册账号后即可使用一张空的本地总表。需要简历分析时，进入“AI 配置”填写：

| 配置项 | 说明 |
|---|---|
| DeepSeek API Key | DeepSeek 开放平台密钥，按用户保存在本地数据库 |
| DeepSeek 模型 | `deepseek-v4-flash` 或 `deepseek-v4-pro` |

API Key 不写入 `.env`，只保存在当前用户的数据库配置中。接口仅返回掩码，不会回显完整密钥。

## 本地数据

每个用户使用独立的本地总表，包含以下字段：

```text
公司名称、秋招岗位、岗位JD、城市、批次、优先级、备注、投递链接、
投递时间、投递截止时间、机考时间、一面、二面、三面、保温、结果、
进展、嵌入式方向、公司/行业类型
```

账号、配置、通知和职位记录保存在 `data/app.db`；简历与分析历史保存在 `data/users/<用户ID>/`。部署服务器时必须持久化并备份这些路径。

## 简历文件

- 支持 `.pdf` 和 `.docx`
- 单文件最大 20 MB
- 文件保存在 `data/users/<用户ID>/resumes/`
- 实际简历文件默认被 Git 忽略
- DOCX 预览提取文本、标题和表格；复杂排版可能与 Word 略有差异
- 扫描版 PDF 若无文本层，AI 分析前需要先执行 OCR

## AI 分析

AI 分析会将以下内容发送到配置的 DeepSeek API：

- 公司名称
- 目标岗位
- 岗位 JD
- 所选简历中提取的文本

分析结果按 Markdown 渲染，包含匹配度、优势、缺口、简历修改建议、面试问题和准备计划。调用前必须先填写 DeepSeek API Key，并确保所选总表记录已有`岗位JD`。

分析工具提供五种模式：综合匹配分析、技术面试训练、HR 面试训练、完整面试流程、简历定向优化。还可以填写特别关注点，要求模型重点分析指定项目、技能或风险。

每次成功分析都会保存到 `data/users/<用户ID>/analysis_history/`。历史记录包含公司、岗位、简历文件名、模型、分析时间和原始 Markdown；分析历史默认被 Git 忽略。

项目内置分析 skill 参考 `jennifer88huang/interview-skills` 的 JD 解析、简历解析、匹配分析和面试题设计流程，并以本项目所需的固定输出结构封装在 `app/prompts/interview_analysis.md` 中。网页后端直接加载该文件，而不是依赖用户目录中的 Codex/OpenClaw skill。

## 依赖

所有 Python 依赖均维护在 `requirements.txt`：

- FastAPI、Uvicorn、requests、python-dotenv
- python-multipart
- python-docx、pypdf
- Markdown、bleach

不需要 Node.js、Playwright 或外部前端构建工具。

## 安全说明

- 浏览器不会读取或保存 DeepSeek API Key 原文
- DeepSeek API Key 按用户保存在本地数据库，接口仅返回掩码
- AI 分析会把所选简历文本发送给 DeepSeek，请确认内容符合你的隐私要求
- 投递记录的删除只会改为“未投递”并清空投递后产生的流程时间
- 只有总表信息中的删除会永久删除当前用户的本地记录，操作前会二次确认
- 服务器部署需要备份并持久化 `data/app.db` 和 `data/users/`

## 技术栈

| 组件 | 技术 |
|---|---|
| 后端 | FastAPI / Uvicorn |
| 数据源 | SQLite（按用户隔离） |
| AI | DeepSeek Chat Completions API |
| 前端 | 原生 HTML / CSS / JavaScript |
| 文档解析 | python-docx / pypdf |
| Markdown | Python-Markdown / bleach |

## 许可

MIT License。

## 更新日志

### v0.2

- 项目名称统一为“校招信息看板”，移除博主与社交平台推广内容
- 适配飞书多维表格字段，支持总表和投递记录实时读取
- 新增投递记录的创建、编辑、删除和一键加入投递功能
- 支持批次、进展、各轮面试时间、岗位 JD、优先级和备注维护
- 新增总表信息页面，公司详情修改可同步回写飞书
- 新增秋招日历，聚合展示投递和招聘流程中的重要日期
- 新增 PDF/DOCX 简历上传、本地保存和网页预览
- 新增 DeepSeek API Key 与模型配置
- 新增综合匹配、技术面试、HR 面试、完整流程和简历优化五种 AI 分析模式
- 分析结果支持安全 Markdown 渲染、本地历史保存、二次预览和 MD 下载
- 完善 Windows 一键安装、完整依赖检查、配置模板和安全说明

### v0.3

- 秋招日历支持"新建日程"：可选择投递、机考、各轮面试、保温、结果、截止等类型，自动写入飞书对应日期字段并推进进展状态
- 新增"其他（自定义）"事件类型：无需绑定公司，自由填写日程内容，数据保存在本地 `data/calendar_events.json`
- 日历图例新增紫色"其他"标记，自定义日程与飞书字段事件在同一视图中合并展示
- 日历工具栏新增"新建日程"按钮，弹窗内置日期选择器，默认填充当天日期

### v0.4

- 多用户系统：注册/登录功能，JWT 认证，密码 bcrypt 哈希存储
- 每用户独立飞书配置、DeepSeek API Key、看板数据缓存
- 每用户独立简历文件、AI 分析历史、本地自定义日程
- 数据持久化到 SQLite（`data/app.db`），支持 WAL 模式并发读写
- 前端登录/注册页面，登录后 token 自动附加到所有 API 请求，401 自动退出
- 侧边栏显示当前用户名和退出按钮
- 服务监听 `0.0.0.0`，支持外网多用户同时访问
- 新增依赖：bcrypt、PyJWT

### v0.5

- 职位总表和投递记录从飞书迁移为本地 SQLite 存储
- 每个用户自动获得独立的空总表，记录按 `user_id` 强制隔离
- 新增、编辑、删除、加入投递、公司详情和记录日历全部改为本地读写
- AI 分析直接读取当前用户的本地岗位与岗位 JD
- 移除飞书配置、应用权限和表格模板依赖，仅保留 DeepSeek AI 配置
- 服务器部署只需持久化 `data/app.db` 与 `data/users/`
