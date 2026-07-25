# Vue 3 前端架构迁移方案

## 现状分析

| 维度 | 当前 | 问题 |
|------|------|------|
| 框架 | 无，原生 JS | 1535行单文件，难以维护 |
| 路由 | 自研 `data-page` + class toggle | 无 URL 历史，无法分享链接 |
| 状态 | 16 个全局 `var` 变量 | 无响应式，手动 DOM 操作 |
| 组件 | 模板字符串拼接 innerHTML | XSS 风险，无法复用 |
| 构建 | 无，直接引用静态文件 | 无热更新，无 Tree-shaking |
| CSS | 5 个独立 CSS 文件 | 无作用域隔离 |

## 技术选型

| 层 | 方案 | 原因 |
|----|------|------|
| 框架 | Vue 3.4+ Composition API | 生态成熟，TS 支持好 |
| 构建 | Vite 5 | 秒级 HMR，开箱即用 |
| 路由 | Vue Router 4 | 官方方案，支持历史模式 |
| 状态 | Pinia | Vue 3 官方推荐 |
| HTTP | 保持现有 `api()` 封装 | 后端 API 不变 |
| CSS | pixelium CSS 变量 + `<style scoped>` | 保留像素风格 |
| UI 库 | 无（手动组件） | 保持像素风格一致性 |

## 组件树拆分

```
App.vue
├── AppLayout.vue
│   ├── SidebarNav.vue          ← 左侧导航
│   ├── Topbar.vue              ← 顶部标题栏 + 通知/设置按钮
│   └── <router-view>
│
├── 页面组件
│   ├── DashboardPage.vue       ← 投递信息（表格+统计+KPI）
│   ├── BoardPage.vue           ← 投递看板（拖拽分列）
│   ├── TotalTablePage.vue      ← 总表信息（个人+共享）
│   ├── ResumePage.vue          ← 简历管理（上传/预览/删除）
│   ├── AiAnalysisPage.vue      ← 简历分析
│   ├── AdminPage.vue           ← 管理页面
│   └── DocsPage.vue            ← 使用文档 (/guide)
│
├── 弹窗组件
│   ├── RecordDetailModal.vue   ← 记录详情/编辑（最复杂，~30字段）
│   ├── ConfigModal.vue         ← AI配置 + 进度跟踪
│   ├── HelpModal.vue           ← 使用帮助
│   ├── TrackerTestModal.vue    ← 同步结果/待确认列表
│   ├── LoginModal.vue          ← 登录/注册
│   ├── OfferCompareModal.vue   ← Offer 对比
│   └── ChatModal.vue           ← 站内聊天
│
├── 通用组件
│   ├── AppButton.vue           ← 按钮（primary/danger/icon）
│   ├── AppTable.vue            ← 数据表格
│   ├── AppCard.vue             ← 卡片容器
│   ├── ProgressBadge.vue       ← 进展标签
│   ├── DatePicker.vue          ← 日期选择
│   ├── ToastNotification.vue   ← Toast 提示
│   ├── ProgressFilter.vue      ← 进展筛选器
│   └── ThemePicker.vue         ← 主题切换器
│
├── 看板组件
│   ├── BoardColumn.vue         ← 单列容器（拖放目标）
│   ├── BoardCard.vue           ← 可拖拽卡片
│   └── CalendarWidget.vue      ← 日历组件
```

## Store 拆分（Pinia）

```
stores/
├── auth.js          ← _token, _currentUser, login/logout
├── dashboard.js     ← _lastData, 总表/投递记录 CRUD
├── tracker.js       ← _trackerPending, 邮箱同步状态
├── chat.js          ← 聊天消息/用户
├── notifications.js ← 通知/提醒
├── resumes.js       ← _resumeFiles, 上传/删除
├── config.js        ← AI 配置状态
└── theme.js         ← 主题切换
```

## 迁移策略：逐页替换

不改后端一行代码。每步产出可独立部署验证。

| 阶段 | 内容 | 工时 |
|------|------|------|
| 1. 脚手架 | Vite + Vue3 + Router + Pinia 项目初始化，保留原 index.html 共存 | 0.5天 |
| 2. 外壳 | AppLayout（Sidebar + Topbar + Router View），登录/注册 | 1天 |
| 3. 通用组件 | Button/Table/Card/Badge/Toast/Modal 基础组件库 | 1天 |
| 4. 投递信息 | DashboardPage（表格+统计+KPI+筛选） | 1.5天 |
| 5. 投递看板 | BoardPage（拖拽分列+进展回退确认） | 1天 |
| 6. 总表信息 | TotalTablePage（个人/共享+记录详情弹窗） | 1.5天 |
| 7. 简历管理 | ResumePage（上传/预览/删除） | 0.5天 |
| 8. 简历分析 | AiAnalysisPage + AI配置弹窗 | 1天 |
| 9. 邮箱跟踪 | 进度跟踪配置 + 同步/测试 + 待确认弹窗 | 1天 |
| 10. 管理页面 | AdminPage（用户管理/邀请码/通知） | 0.5天 |
| 11. 聊天 | ChatModal | 0.5天 |
| 12. 收尾 | 主题系统适配、日历、旧文件清理、部署切换 | 1天 |
| **合计** | | **11天** |

## 关键风险与对策

| 风险 | 对策 |
|------|------|
| 像素风格丢失 | pixelium CSS 变量体系保留，组件内引用 `var(--blue)` 等 |
| 拖拽看板重建复杂 | 复用原 `BOARD_COLUMNS` 逻辑，Vue 版用 `@drop/@dragover` 事件 |
| 记录详情弹窗字段多（~30） | 用 `v-for` 渲染字段配置数组，减少模板重复 |
| API 调用量大 | 保持现有 `api()` 函数签名不变，加请求去重/缓存 |
| 部署兼容 | Vite build 输出到 `static/dist/`，FastAPI 挂载 `StaticFiles` |

## 部署切换

```python
# main.py
app.mount("/assets", StaticFiles(directory="static/dist/assets"), name="assets")

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    # Vue Router history 模式，所有非 API 路径返回 index.html
    if not full_path.startswith("api/"):
        return FileResponse("static/dist/index.html")
```

## 不做的

- 不改后端 API
- 不改数据库
- 不引入 UI 组件库（保持像素风格）
- 不加入 TypeScript（保持低门槛）
- 不加入 SSR/SSG
