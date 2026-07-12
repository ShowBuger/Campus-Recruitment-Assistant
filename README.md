# 校招信息看板

本地运行的校招投递管理工具。项目通过飞书 OpenAPI 读写多维表格，在浏览器中展示投递进度、维护记录、预览简历，并使用 DeepSeek 分析简历与岗位的匹配情况。

**当前版本：v0.3**

## 功能

- 看板总览：公司数量、投递漏斗、截止时间、方向与公司类型分布
- 投递记录：新增和编辑记录；移出投递时保留主表行并重置投递流程
- 总表信息：浏览、编辑和永久删除飞书主表记录，维护优先级、备注和岗位 JD
- 秋招日历：按月查看投递、机考/笔试、面试、保温、结果和截止事件；点击"新建日程"可直接在日历上为已有记录添加日期，或创建无需绑定公司的自定义本地日程
- 简历预览：上传 PDF/DOCX 到本地 `resume/`，直接在网页中预览
- 简历分析：选择简历和总表岗位，调用 DeepSeek 输出 Markdown 分析报告
- 分析历史：分析结果以 JSON 保存在本地 `analysis_history/`，可随时二次预览
- 本地配置：管理飞书凭证、DeepSeek API Key 和模型
- 亮色/暗色主题

## 环境要求

- Python 3.11 或更高版本
- Windows 10/11 推荐使用 `.bat` 脚本，Linux/macOS 使用 `.sh` 脚本
- 可访问 `open.feishu.cn` 和 `api.deepseek.com` 的网络
- 一个已发布的飞书企业自建应用

## 快速安装

### Windows

1. 克隆项目：

```powershell
git clone https://github.com/kaoya-123/embeded_qiuzhao_kanban.git
cd embeded_qiuzhao_kanban
```

2. 双击 `install-deps.bat`，脚本会安装 `requirements.txt` 中的全部依赖。
3. 双击 `start-dashboard.bat`。
4. 打开 `http://localhost:8765`。

### Linux / macOS

1. 克隆项目：

```bash
git clone https://github.com/kaoya-123/embeded_qiuzhao_kanban.git
cd embeded_qiuzhao_kanban
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

## 复制飞书表格模板

项目推荐使用已经适配字段结构的多维表格模板：

**[打开并复制“校招信息看板”飞书多维表格](https://my.feishu.cn/base/FQjJbI4yUaQXzts7cGEcx6dIn2d?from=from_copylink)**

打开链接后，将表格复制到自己的飞书空间，再使用复制后表格的链接、Base Token 和主表 ID 配置看板。不要直接把模板原表作为个人投递表使用。

复制后还需要：

1. 将自己的飞书自建应用添加为该多维表格的协作者。
2. 为应用开通多维表格读写权限并发布应用版本。
3. 在看板“飞书配置”页面粘贴复制后的表格链接和应用凭证。

## 配置

首次打开网页后进入“飞书配置”，填写：

| 配置项 | 说明 |
|---|---|
| App ID | 飞书自建应用 App ID |
| App Secret | 飞书自建应用密钥 |
| Base Token | 多维表格链接或 App Token |
| 主表 ID | 目标数据表的 `table_id` |
| DeepSeek API Key | DeepSeek 开放平台密钥，仅保存在本机 |
| DeepSeek 模型 | `deepseek-v4-flash` 或 `deepseek-v4-pro` |

也可以复制配置模板：

```powershell
Copy-Item .env.example .env
```

```dotenv
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
FEISHU_APP_TOKEN=你的多维表格_token
MAIN_TABLE_ID=tblxxxxxxxx
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_MODEL=deepseek-v4-flash
```

`.env` 已被 Git 忽略。不要提交、截图或分享真实密钥。

## 飞书权限与字段

飞书应用至少需要多维表格读写权限，并需要被添加为目标多维表格的协作者。修改权限后需创建并发布新版本。

看板使用以下主表字段：

```text
公司名称、秋招岗位、岗位JD、城市、批次、优先级、备注、投递链接、
投递时间、投递截止时间、机考时间、一面、二面、三面、保温、结果、
进展、嵌入式方向、公司/行业类型
```

字段类型应与看板匹配：日期列使用日期时间字段，`进展`使用多选，`批次`和`优先级`使用单选，`岗位JD`和`备注`使用文本。

## 简历文件

- 支持 `.pdf` 和 `.docx`
- 单文件最大 20 MB
- 文件保存在项目的 `resume/` 目录
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

每次成功分析都会保存到本地 `analysis_history/`。历史记录包含公司、岗位、简历文件名、模型、分析时间和原始 Markdown；分析历史默认被 Git 忽略。

项目内置分析 skill 参考 `jennifer88huang/interview-skills` 的 JD 解析、简历解析、匹配分析和面试题设计流程，并以本项目所需的固定输出结构封装在 `app/prompts/interview_analysis.md` 中。网页后端直接加载该文件，而不是依赖用户目录中的 Codex/OpenClaw skill。

## 依赖

所有 Python 依赖均维护在 `requirements.txt`：

- FastAPI、Uvicorn、requests、python-dotenv
- python-multipart
- python-docx、pypdf
- Markdown、bleach

不需要 Node.js、Playwright 或外部前端构建工具。

## 安全说明

- 浏览器不会读取或保存飞书 App Secret 与 DeepSeek API Key 原文
- 密钥只保存在本机 `.env`，接口仅返回掩码
- AI 分析会把所选简历文本发送给 DeepSeek，请确认内容符合你的隐私要求
- 投递记录的删除只会改为“未投递”并清空投递后产生的流程时间
- 只有总表信息中的删除会永久删除飞书主表对应行，操作前会二次确认

## 技术栈

| 组件 | 技术 |
|---|---|
| 后端 | FastAPI / Uvicorn |
| 数据源 | 飞书多维表格 Bitable |
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
